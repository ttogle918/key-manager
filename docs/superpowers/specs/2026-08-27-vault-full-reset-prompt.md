<!--
SPDX-FileCopyrightText: 2026 [Your Name]
SPDX-License-Identifier: MIT
-->

# 나중에 쓸 프롬프트 — 금고 원클릭 완전 초기화(VAULT-RESET)

> 대회 제출(2026-08-27) 시점에는 미구현. `docs/RESULT_REPORT.md` §8·`docs/RESULT_REPORT_제출양식.md`
> 로드맵 ⑤에 정직하게 명시해뒀다. 아래 프롬프트를 그대로 붙여넣어 착수한다.

```
교육·공용 PC 시나리오를 위한 "금고 원클릭 완전 초기화" 기능을 구현하고 싶어.

배경: 사이드바의 "프로토타입 데이터 초기화" 버튼(frontend/src/store/keylensStore.ts의
resetProto)은 프론트엔드 화면 상태만 리셋하고, 백엔드 vault.db의 실제 암호화 항목은
전혀 지우지 않아. 완전 초기화는 지금 항목별 삭제(DELETE /vault/entries/{id})나 번들
교체(가져오기, vault_repo.py의 replace_with_bundle)로만 가능해.

원하는 것: 인증(잠금 해제)된 상태에서 버튼 하나로 금고를 완전히 비우고 "초기화 안 됨"
상태로 되돌리는 기능. 확인 대화상자(되돌릴 수 없다는 경고) 필수.

먼저 superpowers:brainstorming으로 설계를 논의해줘 — 특히 이 두 가지를 결정해야 해:
1. "완전 초기화"의 의미: vault.db 파일 자체를 삭제하고 /vault/init부터 다시 시작하게
   할지, 아니면 vault_repo.py의 DELETE FROM entries/meta/access_log 를 재사용해서
   "초기화되지 않은 금고" 상태로 되돌릴지 (마스터 비밀번호도 다시 설정해야 하는지 여부
   포함).
2. 엔드포인트 인증 요구사항: 다른 파괴적 작업(change-password)처럼 현재 마스터
   비밀번호 재확인을 요구할지, 아니면 이미 잠금 해제된 세션이면 충분한지.

설계가 정해지면 superpowers:writing-plans로 계획을 쓰고, superpowers:test-driven-
development로 구현해줘. 지켜야 할 이 레포 관례:

- 새 파일 SPDX 헤더 2줄 필수(`[Your Name]` 리터럴 그대로 — 실제 이름으로 바꾸지 않음).
- 새 런타임 의존성 추가 금지.
- httpx/TestClient 쓰지 않음(certifi MPL-2.0 라이선스 이슈로 이 레포에서 금지된 패턴,
  backend/requirements-dev.txt에 명시) — 라우트 함수를 직접 호출해서 테스트
  (backend/tests/test_vault_api.py 패턴 참고).
- 백엔드: 새 엔드포인트(예: POST /vault/reset)는 vault_session.py의 인증 상태를 확인하고,
  vault_repo.py에 이미 있는 전체 삭제 SQL(DELETE FROM entries/meta/access_log)을 재사용
  하는 방향을 우선 검토.
- 프론트: 사이드바의 "프로토타입 데이터 초기화" 버튼을 이 실제 API를 호출하는 버튼으로
  교체(라벨도 실제 동작을 정확히 설명하도록 변경 — 예: "금고 완전 초기화"). 확인
  모달(Modals.tsx 패턴) 추가, 성공 시 setup 화면으로 이동.
- 완료 후 docs/RESULT_REPORT.md §8·docs/RESULT_REPORT_제출양식.md 로드맵 항목을
  "구현 완료"로 갱신하고, 이 스펙 파일(vault-full-reset-prompt.md)은 삭제하거나
  구현 완료 표시로 갱신.
- 검증: 백엔드 pytest 추가(인증 안 된 상태에서 403/401, 인증된 상태에서 초기화 후
  /vault/status가 초기화 안 됨을 반환하는지), 프론트 tsc/oxlint/build.
```
