<!--
SPDX-FileCopyrightText: 2026 [Your Name]
SPDX-License-Identifier: MIT
-->

# 금고 완전 초기화(VAULT-RESET) 설계

> `docs/superpowers/specs/2026-08-27-vault-full-reset-prompt.md`(작성자가 미리 써둔 착수 프롬프트)를
> 그대로 브레인스토밍에 붙여넣어 시작했다. 교육·공용 PC 시나리오에서 버튼 하나로 금고를 완전히
> 비우고 "초기화 안 됨" 상태로 되돌리는 기능.

## 배경

사이드바의 "프로토타입 데이터 초기화" 버튼(`frontend/src/store/keylensStore.ts`의 `resetProto`)은
프론트엔드 화면 상태만 리셋하고, 백엔드 `vault.db`의 실제 암호화 항목은 전혀 지우지 않는다. 완전
초기화는 지금 항목별 삭제(`DELETE /vault/entries/{id}`)나 번들 교체(가져오기,
`vault_repo.replace_with_bundle`)로만 우회적으로 가능하다. 공용 PC에서 시연·교육 후 다음 사용자를
위해 완전히 비우는 직접적인 방법이 없다.

## 스코프

- ✅ **포함**: `POST /vault/reset` 엔드포인트, 금고 데이터 전체 삭제(항목·메타·감사이력·SDK
  디렉토리 승인 기록), 프론트 확인 모달(비밀번호 재입력) + 사이드바 버튼 교체.
- ❌ **범위 밖**: `vault.db` 파일 자체 삭제, 삭제 전 자동 백업/내보내기 유도(이미 SYNC-0 내보내기가
  있으므로 별도 안내 없음), rate-limit 신설(기존 `change-password`와 동일하게 비보호 — 아래 판단 2
  참고).

## 핵심 설계 판단

### 판단 1 — 파일 삭제 대신 기존 DELETE 문 재사용

**결정**: `vault_repo.py`에 `reset_vault(conn)`을 신설해 `DELETE FROM access_log/entries/meta/
sdk_project_dirs/sdk_pending_requests`를 원자적으로 실행한다. `vault.db` 파일 자체는 건드리지
않는다.

**왜**: `replace_with_bundle`이 이미 `DELETE FROM access_log/entries/meta`를 프로덕션에서 검증된
형태로 쓰고 있다 — 같은 패턴 재사용. `meta` 테이블의 id=1 행이 사라지면 `is_initialized()`(`SELECT 1
FROM meta WHERE id=1`)가 자동으로 `False`를 반환해 "초기화 안 됨" 상태가 그냥 따라온다 — 별도 상태
플래그가 필요 없다. 파일 삭제는 SQLite WAL/저널 파일 잔존, OS별 파일 잠금 등 불필요한 위험을 추가할
뿐 이득이 없다.

**SDK 테이블도 포함**: 사용자 프롬프트엔 없었지만 브레인스토밍에서 결정 — `sdk_project_dirs`·
`sdk_pending_requests`(RUNTIME-1, "이 디렉토리는 이 프로젝트 키를 가져가도 됨" 승인 기록)를 안 지우면
공용 PC의 다음 사용자에게 이전 사용자의 로컬 디렉토리 승인 흔적이 남는다 — "완전 초기화"라는 이름에
안 맞음.

### 판단 2 — 비밀번호 재입력 필수(세션이 잠금 해제 상태라도)

**결정**: `/vault/reset`은 현재 세션의 unlock 여부(`_require_key()`)를 확인하지 않는다. 대신
`vault_repo.unlock(conn, password)`으로 제공된 비밀번호가 실제 현재 마스터 비밀번호와 일치하는지
**항상** 독립적으로 검증한다(반환된 키는 버림 — `change_password`가 이미 쓰는 것과 동일한 검증
전용 호출 기법).

**왜**: 이 기능의 동기 자체가 "교육·공용 PC" 시나리오다 — 잠금 해제된 채 방치된 세션만으로 완전
삭제를 허용하면, 지나가던 사람이 비밀번호도 모른 채 데이터를 지울 수 있다는 뜻이라 위협모델과
정확히 어긋난다. 기존 `change_password` 엔드포인트도 세션 unlock 상태와 무관하게 `old_password` 자체
검증만으로 동작하는 동일한 패턴이라, 이 앱의 기존 "재인증 요구 파괴적 작업" 관례를 그대로 따른다.
rate-limit(`VaultService.unlock`의 지수 백오프)은 이 검증 경로에 없다 — `change_password`도 마찬가지
(모듈 레벨 `vault_repo.unlock`을 직접 호출, 세션의 백오프 로직을 안 거침). 새로 보호를 추가하는 건
이번 스코프 밖(이미 존재하는 동일 클래스 엔드포인트와의 일관성 우선, 별도 이슈로 남길 만함).

### 판단 3 — 프론트: 기존 버튼 교체 + 비밀번호 확인 모달

**결정**: 사이드바 "프로토타입 데이터 초기화" 버튼을 "금고 완전 초기화"로 라벨·동작 교체. 클릭 시
`DeleteModal` 패턴을 따르는 새 확인 모달을 연다 — 경고 문구("되돌릴 수 없습니다") + 비밀번호
입력칸(`LockScreen`처럼 틀리면 인라인 빨간 에러) + 확인/취소 버튼. 성공하면 기존 `resetProto`가
이미 하는 화면 상태 리셋 로직을 재사용해 setup 화면으로 이동.

**왜**: 별도의 "RESET이라고 입력하세요" 같은 2차 확인 문구 입력은 추가하지 않는다 — 비밀번호
재입력 자체가 이미 강한 확인 게이트이고(모르면 못 지움), 이 앱의 다른 파괴적 확인(삭제)도 단순
확인/취소 모달 수준이라 과설계를 피한다.

## 데이터/스키마 변경 요약

| 위치 | 변경 |
|---|---|
| `backend/app/vault_repo.py` | `reset_vault(conn) -> None` 신설(원자적 DELETE 5개 테이블) |
| `backend/app/vault_session.py` | `VaultService.reset(password: str) -> None` 신설 — 비밀번호 검증 후 `reset_vault` 호출, 마지막에 `self.lock()` |
| `backend/app/main.py` | `POST /vault/reset`(body: 기존 `VaultPassword` 재사용, response: `VaultStatus`) — 401(틀린 비번)/409(미초기화) 매핑은 `vault_unlock`과 동일 패턴 |
| `frontend/src/api/client.ts` | `vaultApi.reset(password: string): Promise<VaultStatus>` |
| `frontend/src/store/keylensStore.ts` | `resetVaultOpen/resetVaultPw/resetVaultErr/resettingVault` 상태 + `openResetVault/closeResetVault/setResetVaultPw/confirmResetVault` 액션(성공 시 기존 `resetProto` 재사용) |
| `frontend/src/components/modals/Modals.tsx` | `ResetVaultModal` 신설 |
| `frontend/src/components/Sidebar.tsx` | 버튼 라벨·핸들러 교체(`resetProto` 직접 호출 → 모달 오픈) |

## 테스트 전략

- **백엔드**: `test_vault_api.py`에 케이스 추가 — (1) 틀린 비밀번호로 reset → 401, 기존 데이터 무손상,
  (2) 올바른 비밀번호로 reset → 성공 후 `vault_status().initialized is False`, (3) reset 후 재-`init`
  가능(같은 비밀번호로도), (4) SDK 디렉토리 승인 기록도 reset 후 사라짐(`list_project_dirs` 빈 목록).
  httpx/TestClient 안 씀 — 라우트 함수 직접 호출(기존 관례).
- **프론트**: 컴포넌트 테스트 인프라 없음(기존 관례) — `tsc --noEmit -p tsconfig.app.json` / `oxlint` /
  `npm run build`로 검증.

## 완료 후 후속 작업

- `docs/RESULT_REPORT.md` §8·`docs/RESULT_REPORT_제출양식.md` 로드맵 항목을 "구현 완료"로 갱신
  (원 프롬프트 파일의 지시사항).
- `docs/superpowers/specs/2026-08-27-vault-full-reset-prompt.md`(착수 프롬프트 파일)는 구현 완료 후
  삭제하거나 "구현 완료" 표시로 갱신.
