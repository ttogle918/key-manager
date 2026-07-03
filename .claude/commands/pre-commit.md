---
description: 커밋·제출 전 4대 점검 — 라이선스 / SPDX / 시크릿 / 재현성
allowed-tools: Bash, Read, Grep, Glob
---

# 커밋·제출 전 체크리스트 (CLAUDE.md 기준)

아래 4개 검사를 모두 수행하고, 하나라도 실패하면 **커밋을 진행하지 말고** 실패 항목을 보고하라.

## 1. 라이선스
`/license-check` 커맨드의 1~4번 절차를 수행한다. 카피레프트 0건, SPDX 헤더 누락 0건이어야 통과.

## 2. 시크릿 스캔 (이 프로젝트는 키 관리 도구라 특히 중요)
```bash
# 스테이징된 변경분 + 전체 트리에서 실제 키 패턴 탐지
git diff --cached | grep -nE "sk-[A-Za-z0-9]{20,}|ghp_[A-Za-z0-9]{36}|AKIA[0-9A-Z]{16}|AIza[0-9A-Za-z_-]{35}|xox[bpars]-[0-9A-Za-z-]{10,}" || echo "diff clean"
grep -rnE "sk-[A-Za-z0-9]{20,}|ghp_[A-Za-z0-9]{36}|AKIA[0-9A-Z]{16}|AIza[0-9A-Za-z_-]{35}" --include="*.py" --include="*.ts" --include="*.tsx" --include="*.md" --include="*.yaml" --include="*.json" . || echo "tree clean"
```
- 매칭이 나오면 그것이 **명백한 더미**(`sk-xxxxxxxx`, `sk-dummy...` 등 규칙적 placeholder)인지 판정하라. 실제 키로 보이는 고엔트로피 문자열이면 🚨 즉시 중단.
- `.gitignore`에 `.env`, `*.sqlite`, `*.sqlite3`, `*.db`, `credentials*.json`, `*.pem`, `*.key`가 포함되어 있는지 확인.
- `git status`에 위 파일들이 추적 대상으로 잡히지 않는지 확인.

## 3. 테스트
```bash
pytest -q
```
- 실패 테스트가 있으면 목록을 보고. (프론트 테스트가 있으면 `npm test -- --watchAll=false`도 수행)

## 4. 재현성 스모크 테스트
- `README.md`의 설치·실행 명령이 현재 코드와 일치하는지 대조 (의존성 추가/스크립트 변경 후 README 미갱신이 가장 흔한 불일치).
- `requirements.txt` / `package.json`의 버전이 고정(pinned)되어 있는지 확인. 범위 지정(`>=`, `^`, `~`)이 새로 들어왔다면 보고.

## 출력
4개 항목의 ✅/🚨 요약표 + 실패 시 구체적 파일·라인. 모두 통과 시에만 "커밋 가능" 판정.
