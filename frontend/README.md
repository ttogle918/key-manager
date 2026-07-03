<!--
SPDX-FileCopyrightText: 2026 [Your Name]
SPDX-License-Identifier: MIT
-->

# KeyLens — 프론트엔드 (web UI)

Claude Design 프로토타입(`KeyLens 자격증명 관리 도구/KeyLens.dc.html`)을 실제 React 코드로 이식한 프론트엔드다.
현재는 **프론트엔드 단독 목업**으로, seed 데이터와 시뮬레이션된 분석/저장으로 전체 화면·인터랙션을 재현한다.
실제 분류·OCR·암호화(SPEC 5장의 FastAPI 백엔드)는 이후 `src/data/`·`src/store/`의 경계에서 교체한다.

## 기술 스택 (전부 permissive 라이선스)

| 영역 | 선택 | 라이선스 |
|---|---|---|
| 빌드/프레임워크 | Vite + React 19 + TypeScript | MIT |
| 스타일링 | Tailwind CSS v4 (`@theme` 디자인 토큰) | MIT |
| 접근성 프리미티브 | Radix UI (Dialog) | MIT |
| 상태관리 | Zustand | MIT |
| 아이콘 | lucide-react | ISC |
| 유틸 | clsx, tailwind-merge | MIT |

## 실행

```bash
cd frontend
npm install       # 최초 1회
npm run dev       # 개발 서버 (기본 http://localhost:5173)
```

빌드/미리보기:

```bash
npm run build     # tsc 타입체크 + 프로덕션 번들 (dist/)
npm run preview   # 빌드 결과 로컬 서빙
```

## 데스크톱 배포 (후행)

현재는 로컬 웹앱으로 개발한다. 데스크톱 셸(PyWebView 또는 Tauri)은 안정화 단계에서
이 `frontend/` 빌드를 그대로 감싸는 방식으로 붙인다 — React 코드는 변경되지 않는다.

## 구조

```
src/
  types.ts                 도메인 타입
  data/services.ts         서비스 지식베이스(TYPE_MAP·SVC_META) — 백엔드 YAML 교체 지점
  data/seed.ts             시연용 seed 보관함 + 목업 분석 결과 (전부 더미 값)
  lib/                     cn(클래스 병합), format(날짜·강도·.env 직렬화)
  store/keylensStore.ts    Zustand 스토어 — 프로토타입 DCLogic 이식
  store/selectors.ts       파생 셀렉터(프로젝트 목록 등)
  components/
    Sidebar.tsx            앱 셸 사이드바
    screens/               Setup / Lock / Input / Vault 화면
    input/ResultCard.tsx   분석 결과 카드(신호 충돌 해소 포함)
    vault/VaultRow.tsx     보관함 항목 행 + 상세
    modals/Modals.tsx      삭제 / 중복 / .env 내보내기 다이얼로그
    ui/                    Modal(Radix), Toast
```

> ⚠️ 시크릿 위생(CLAUDE.md): `src/data/seed.ts`의 모든 값은 명백한 더미(placeholder)다. 실제 키를 커밋하지 말 것.
