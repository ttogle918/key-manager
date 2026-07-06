<!--
SPDX-FileCopyrightText: 2026 [Your Name]
SPDX-License-Identifier: MIT
-->
## 무엇을 바꿨나
<!-- 한두 문장 요약. 관련 이슈가 있으면 "Closes #번호" -->

## 유형
- [ ] 새 서비스 지식베이스(YAML)
- [ ] 기능(feat)
- [ ] 버그 수정(fix)
- [ ] 문서(docs)
- [ ] 리팩터/기타

## 체크리스트 (CONTRIBUTING.md 기준)
- [ ] 새 파일 맨 위에 **SPDX 헤더 2줄**
- [ ] **실제 키·시크릿 없음** — 예시·테스트는 더미(`sk-xxxxxxxx`)만
- [ ] 새 의존성은 **permissive만**(MIT/Apache-2.0/BSD/ISC) — 카피레프트(GPL/AGPL/LGPL/MPL) 없음
- [ ] 백엔드 변경 시 `pytest -q` 통과 / 프론트 변경 시 `npm run build` 통과
- [ ] `reuse lint` 통과, 관련 문서(README·SBOM 등) 갱신
- [ ] (새 서비스) 값 정규식은 **공식 문서 기준** 작성, 오탐 방지 테스트 추가
