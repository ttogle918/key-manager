---
description: 작업 한 단위 마무리 — 검증 → 4대 점검 → 백로그·문서 동기화 → 커밋
allowed-tools: Bash, Read, Grep, Glob, Edit
---

# 작업 마무리 (/done)

방금 끝낸 작업 한 단위를 **검증하고 깔끔하게 커밋**하는 루틴이다. 아래 순서대로 수행하고,
게이트(2·3)에서 하나라도 실패하면 **커밋하지 말고** 실패 항목을 보고한 뒤 멈춰라.

인자로 커밋 메시지 제목이 주어지면(`/done <제목>`) 그것을 커밋 제목으로 쓰고, 없으면 변경 내용에서 직접 짓는다.

## 1. 변경 파악
```bash
git status --short
git diff --stat
```
- 무엇이 바뀌었는지 한 줄로 요약한다(어느 영역: frontend / backend / knowledge / docs).
- 변경이 없으면 여기서 멈추고 "커밋할 변경 없음"을 보고.

## 2. 검증 (변경 영역에 맞게) — 게이트
- **backend/ 변경 시**: `cd backend && ./.venv/Scripts/python.exe -m pytest -q` (venv 없으면 `python -m pytest -q`). 실패 0이어야 통과.
- **frontend/ 변경 시**: `cd frontend && npm run build` (tsc 타입체크 + 번들). 에러 0이어야 통과.
- 런타임 동작이 바뀐 변경이면 가능한 범위에서 스모크(서버 `/health`, 앱 로드)로 실제 동작을 한 번 확인한다. 테스트·문서만 바뀐 변경은 생략 가능.

## 3. 4대 점검 — 게이트
`/pre-commit`의 4개 검사(**라이선스 / 시크릿 / 테스트 / 재현성**)를 수행한다.
- 특히 이 프로젝트는 키 관리 도구다 — 스테이징 diff에 **실제 키**가 없는지, 새 의존성에 **카피레프트(GPL/AGPL/LGPL/MPL)**가 없는지 반드시 확인.
- 새 파일에 **SPDX 헤더** 두 줄이 있는지 확인(CLAUDE.md).

## 4. 백로그·문서 동기화
- 이번 작업으로 완료된 `docs/BACKLOG.md`의 TASK 체크박스를 갱신하고, 진행 상황 표시를 최신화한다.
- 의존성·실행 방법이 바뀌었으면 관련 `README.md`(루트/frontend/backend)를 코드와 일치시킨다.

## 5. 커밋
- 현재 브랜치 확인. 기본 브랜치(main)에서의 커밋은 이 프로젝트의 솔로 워크플로에 맞춰 허용한다.
- 관련 파일만 스테이징한다. `node_modules/`, `dist/`, `.venv/`, `__pycache__/`, `.env`, `*.sqlite`가 스테이징에 **절대 포함되지 않았는지** `git diff --cached --name-only`로 확인.
- **Conventional Commit** 형식 + 한국어 본문으로 커밋한다. 예: `feat(backend): …`, `docs: …`, `fix(frontend): …`.
- 커밋 메시지 마지막 줄에 반드시 아래를 포함:
  ```
  Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>
  ```
- 푸시는 하지 않는다(사용자가 명시적으로 요청할 때만).

## 6. 요약 보고
- 커밋 해시 + 한 줄 요약, 게이트 결과(✅/🚨), 백로그에서 닫힌 TASK, 남은 후속 작업 1~2개를 보고한다.
