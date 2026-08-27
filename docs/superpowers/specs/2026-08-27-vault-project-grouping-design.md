<!--
SPDX-FileCopyrightText: 2026 [Your Name]
SPDX-License-Identifier: MIT
-->

# 보관함 프로젝트별 그룹핑 + 서비스 로고 태그 필터 설계

> 지금 보관함(VaultScreen)은 **서비스별**(Notion·Kakao·GCP…)로 그룹핑돼 있다. 사용자는 대신
> **프로젝트별**로 묶이길 원한다 — `keylens-env` SDK(RUNTIME-1)가 이미 "프로젝트 = 컬렉션" 단위로
> 키를 가져가므로, 보관함 화면도 같은 축으로 보이는 게 실제 사용 패턴과 맞다. 서비스는 대신 상단의
> **로고 태그**로 승격해 "이 서비스 키만 프로젝트 횡단으로 보기" 필터 역할을 한다.

## 배경

`VaultItem.project`는 이미 존재하는 필드다(RUNTIME-1에서 `keylens-env`가 프로젝트 스코프 접근범위를
구현하며 추가). 지금 보관함 UI는 이 필드를 "필터"로만 쓰고(`projFilter` 드롭다운), 그룹핑 축은
여전히 서비스다. 반대로 뒤집는다: **프로젝트가 1차 그룹, 서비스는 프로젝트 안의 소그룹이자 상단
필터 태그**.

부수적으로, 지금까지 대부분의 키는 프로젝트를 안 적고 저장돼 왔다(선택 입력이라). 프로젝트가 1차
그룹이 되면 "프로젝트 없음" 항목이 화면 대부분을 차지하는 어색한 빈 버킷이 생긴다 — 그래서 프로젝트
미지정 시 **등록일(날짜)을 프로젝트명으로 자동 사용**한다.

## 스코프

- ✅ **포함**: 보관함 그룹핑 축을 프로젝트로 전환(서비스는 소그룹), 프로젝트 섹션 아코디언(접기/펼침),
  상단 서비스 로고 태그 다중 선택 필터, 프로젝트 미지정 시 등록일 기본값(백엔드에서 실제 저장),
  기존 `projFilter` 드롭다운을 "섹션으로 스크롤+펼침" 용도로 재활용, `.env 복사`를 프로젝트/서비스
  두 레벨 모두에서 제공.
- ❌ **범위 밖**: 프로젝트 이름 변경/병합 UI(지금처럼 각 항목의 프로젝트 입력칸을 개별 수정하는
  방식 유지), 프로젝트 단위 일괄 삭제·이동, `keylens-env` SDK 쪽 변경(이미 완료된 RUNTIME-1 그대로),
  서비스 로고를 KB YAML에서 서비스별로 커스터마이즈하는 기능(지금은 프론트에 번들된 고정 세트).

## 핵심 설계 판단

### 판단 1 — 프로젝트 미지정 시 "등록일"을 실제 project 값으로 저장(백엔드)

**결정**: `POST /vault/entries`(`vault_add`)에서 `project`가 비어 있으면 오늘 날짜(`YYYY-MM-DD`, UTC)를
**실제 `project` 컬럼에 저장**한다(화면 표시용 임시값이 아님). `PATCH /vault/entries/{id}`
(`vault_update`)에서 사용자가 프로젝트 입력칸을 지워 빈 값을 보내면, "오늘"이 아니라 **그 항목의
`created_at` 날짜**로 되돌린다 — 수정 행위 자체가 프로젝트를 오늘 날짜로 바꿔버리면 안 되므로.

**왜**: 사용자가 명시적으로 "실제 필드에 저장"을 선택했다 — 화면에서만 날짜를 보여주고 저장은 빈
값으로 남기면, `keylens-env`가 이 항목을 "전역 키"로 취급해버려(프로젝트 미지정 = 전역이 기존
RUNTIME-1 규칙) 사용자 의도(그 날짜에 저장한 것들끼리 하나의 컬렉션)와 어긋난다. 실제 필드에 쓰면
그 날짜 문자열이 그대로 `keylens-env`의 `project = "2026-08-27"` 같은 컬렉션명으로도 즉시 쓸 수 있다.

**기존 저장 데이터(마이그레이션 없음)**: 이미 저장된 빈-프로젝트 항목들은 소급 수정하지 않는다.
프론트 그룹핑 계산 시에만 `it.project || dateOnly(it.addedAt)`로 키를 유도해 같은 날짜 섹션에
자연스럽게 들어가게 한다 — 화면엔 빈 버킷이 절대 안 보이지만, 사용자가 그 항목을 직접 한 번 더
저장/수정하기 전까진 DB엔 여전히 빈 문자열로 남는다(다음에 그 항목을 PATCH하면 판단 1의 규칙이
적용되며 자연히 채워짐).

### 판단 2 — 그룹핑 축 전환: 프로젝트(1차) → 서비스(2차 소그룹)

**결정**: `VaultScreen`의 최상위 그룹을 `SERVICE_ORDER` 대신 프로젝트명으로 바꾼다. 각 프로젝트
섹션 안에서는 지금과 동일하게 서비스별 미니 헤더(`SVC_META` 타일/색 재사용)로 나뉘고, 그 안의 항목
정렬(만료 임박 우선)도 그대로 유지한다.

**프로젝트 섹션 정렬**: 그 프로젝트에 속한 항목 중 가장 최근 `addedAt` 기준 내림차순 — 방금 저장한
프로젝트가 항상 위로 온다.

**공통 그룹핑 키**: 프론트에 `projectKey(it) = it.project || dateOnly(it.addedAt)` 헬퍼 하나를 두고
그룹핑·아코디언 펼침 판단·`envCopyProject`·`projFilter` 드롭다운 목록까지 전부 이 함수로 통일한다.
판단 1의 마이그레이션 없음 방침 때문에 일부 기존 항목은 DB엔 여전히 `project`가 빈 문자열일 수
있는데, 이 헬퍼를 안 쓰고 `it.project === name`으로 직접 비교하는 곳이 하나라도 남으면 그 항목만
그룹에서 빠지거나 `.env` 복사에서 누락되는 불일치가 생긴다.

### 판단 3 — 아코디언: 다중 펼침 + 필터 시 자동 펼침

**결정**: 각 프로젝트 섹션은 독립적으로 접기/펼침 가능하고 **여러 개 동시에 펼쳐둘 수 있다**(store에
`expandedProjects: Set<string>` 추가). 보관함 진입 시 기본값은 **가장 최근 프로젝트 하나만 펼침**,
나머지는 접힘.

검색어(`search`)나 서비스 태그 필터가 활성 상태면, **일치하는 항목이 있는 섹션은 수동 펼침 여부와
무관하게 강제로 펼쳐 보인다**(계산: `isOpen = expandedProjects.has(name) || (filterActive && matchCount > 0)`).
`expandedProjects` 자체는 건드리지 않으므로, 필터를 지우면 원래의 수동 펼침 상태로 그대로 돌아간다.

### 판단 4 — 서비스 로고 태그: 다중 선택 필터 + 로컬 SVG + 호버 툴팁

**결정**: 보관함 헤더에 서비스별 로고 태그 행을 추가한다(9종: Notion/Kakao/GCP/OpenAI/Ollama/GitHub/
AWS/Slack/Stripe — CORE-4 지식베이스와 동일 집합). 클릭으로 **다중 선택** 토글, 선택된 서비스만
프로젝트 섹션들 안에서 남기고 나머지는 숨긴다(섹션 구조 자체는 유지, 판단 3의 자동 펼침과 결합).
각 태그는 `title` 속성으로 마우스 호버 시 표시명(Notion, GCP, OpenAI…)을 보여준다.

**로고 소싱**: simple-icons(SVG, **CC0-1.0** — 저작권은 포기되지만 **상표권은 각 브랜드사 소유**로
라이선스에 명시)에서 필요한 9개 파일만 골라 `frontend/src/assets/logos/*.svg`로 **로컬에 커밋**한다.
용량이 작아(파일당 1~2KB) OCR 모델처럼 매번 벤더링할 필요 없이 그냥 저장소에 포함시키고, `simple-icons`
패키지는 파일을 뽑아올 때만 쓰는 devDependency로 둔다(런타임 코드가 import하지 않음 — 런타임
의존성 0). 상표 사용 근거(서비스 식별을 위한 지시적/한정적 사용, nominative fair use — 비밀번호
관리자류 앱에서 보편적인 관행)를 `THIRD-PARTY-NOTICES.md`에 기록한다.

**폴백**: `/knowledge`로 새로 추가된 서비스(로고 파일 없음)는 태그에서 기존 `SVC_META`/`AUTO_PALETTE`
컬러 이니셜 타일로 자동 폴백한다 — 프론트 코드 0줄 확장성 원칙(CORE-4) 유지.

### 판단 5 — 기존 컨트롤 마이그레이션

- **`projFilter` 드롭다운**: 제거하지 않고 유지하되 의미를 바꾼다 — 선택 시 그 프로젝트 섹션으로
  스크롤(`scrollIntoView`) + 강제 펼침(`expandedProjects`에 추가). 더 이상 "필터"가 아니다(그룹
  구조 자체가 프로젝트라 필터링이 불필요해짐).
- **`.env 복사`**: 기존 `envCopyGroup(serviceName)`(서비스 필터)은 그대로 두고 서비스 소그룹
  헤더에 남긴다. 새 `envCopyProject(projectName)`을 추가해 프로젝트 섹션 헤더에도 놓는다(그
  프로젝트의 모든 서비스 항목을 합쳐 `.env` 복사).
- **검색창**: 기존 로직(varName/type/service/memo/context/project 매칭) 그대로 재사용 — 프로젝트
  그룹 구조 위에서 판단 3의 자동 펼침 규칙만 새로 적용된다.

## 데이터/스키마 변경 요약

| 위치 | 변경 |
|---|---|
| `backend/app/main.py` `vault_add` | `project` 공백/None → 오늘 날짜(UTC, `YYYY-MM-DD`)로 채워 `VAULT.add_entry` 호출 |
| `backend/app/main.py` `vault_update` | `project`가 빈 문자열로 오면 해당 항목 `created_at`의 날짜 부분으로 대체 |
| `backend/app/vault_repo.py` | 변경 없음(이미 `project: str \| None` 그대로 받음) |
| `frontend/src/types.ts` | 변경 없음(`VaultItem.project: string` 이미 존재) |

## UI 컴포넌트 변경 요약

| 파일 | 변경 |
|---|---|
| `frontend/src/components/screens/VaultScreen.tsx` | 그룹핑을 서비스→프로젝트로 전환, 서비스 로고 태그 행 추가, 아코디언 렌더링 |
| `frontend/src/store/keylensStore.ts` | `expandedProjects: Set<string>`, `serviceTagFilter: Set<string>`, `toggleProjectSection`, `toggleServiceTag`, `envCopyProject` 추가. `setProjFilter`는 "스크롤+펼침" 사이드이펙트로 변경 |
| `frontend/src/data/services.ts` | 서비스명 → 로고 SVG 경로 매핑 테이블 추가(없으면 기존 타일 폴백) |
| `frontend/src/assets/logos/*.svg` (신규) | simple-icons에서 뽑은 9개 SVG |
| `THIRD-PARTY-NOTICES.md` | simple-icons 출처·CC0·상표 고지 근거 기록 |

## 테스트 전략

- **백엔드**: `test_vault_api.py`에 케이스 추가 — (1) `project` 미지정 저장 → 응답의 `project`가
  오늘 날짜인지, (2) 기존 항목 PATCH로 `project`를 빈 문자열로 보내면 그 항목의 `created_at` 날짜로
  되돌아오는지.
- **프론트**: 이 레포는 컴포넌트 자동 테스트 인프라가 없다(기존 관례, screenshot-explain 계획과
  동일). `tsc --noEmit` + `oxlint` + `npm run build`로 타입/빌드 검증, 그룹핑·아코디언·필터 로직은
  브라우저 수동 확인(체크리스트로 플랜에 명시).
- **로고 자산**: 9개 파일이 실제로 로드되는지(깨진 이미지 없음) 브라우저 수동 확인.

## 범위 밖

프로젝트 이름 변경/병합, 프로젝트 일괄 삭제, 서비스 로고 커스터마이즈(KB YAML 연동), 로고 세트를
9종 이상으로 확장하는 것(새 서비스는 폴백 타일로 충분 — 필요해지면 후속 태스크).
