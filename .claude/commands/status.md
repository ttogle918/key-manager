---
description: 진행 현황 한눈에 — git 상태 + docs/BACKLOG.md 진행률. 코드 변경 없음.
allowed-tools: Bash, Read, Grep, Glob
---

# /status — 프로젝트 진행 현황

코드를 바꾸지 않고, 지금 어디까지 왔는지 빠르게 파악한다. (key-manager는 스프린트 파일이 아니라
플랫 `docs/BACKLOG.md`를 정본으로 쓴다 — 그 구조를 읽는다.)

## 1. 정보 수집

```bash
git branch --show-current
git log --oneline -8
git status --short
```

`docs/BACKLOG.md`에서 파악:
- 스프린트 편성 표(S1~제출)와 현재 스프린트
- 각 TASK 헤더의 상태 표식: `✅ 완료` / `🔄 진행` / `⏳ 대기` / 미표기(미착수)
- 하위 체크박스 `[x]`/`[ ]` 개수로 TASK별 진행률

미커밋 변경이 있으면 어떤 영역(frontend/backend/knowledge/docs)인지 한 줄 요약.

## 2. 현황 출력 (아래 형식)

```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
📊 KeyLens 현황  ·  브랜치: <branch>
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

TASK 진행 (BACKLOG 기준)
  ✅ 완료 :  CORE-1/2/3/4, DEMO-1, VAULT-1/2 …
  🔄 진행 :  <있으면>
  ⏳ 다음 :  <미착수 중 우선순위 높은 1~2개>

최근 커밋 (5줄)
  <해시> <제목>
  …

작업 트리
  <깨끗 / 변경 영역 요약>

다음 추천 작업
  1. <BACKLOG·감사 기준 우선순위 1~2개>
```

## 3. 규칙
- **코드·문서를 수정하지 않는다.** 읽기·요약만.
- BACKLOG 상태 표식과 실제 커밋이 어긋나면(예: 코드는 됐는데 체크박스 미갱신) 그 불일치를 한 줄로 지적한다.
- 남은 후속은 `SECURITY_REVIEW.md`의 ⏳ 항목도 함께 훑어 반영한다.
