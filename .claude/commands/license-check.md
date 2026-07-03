---
description: 전체 의존성 라이선스 스캔 + SPDX 헤더 검증 (대회 2차 라이선스 검증 사전 통과용)
allowed-tools: Bash, Read, Grep, Glob
---

# 라이선스 셀프 검증

대회 2차 평가는 라이선스 충돌·위반을 직접 검증한다. 아래를 순서대로 수행하고 결과를 표로 보고하라.

## 1. Python 의존성 스캔
```bash
pip-licenses --format=markdown --with-urls
```
- 결과에서 다음 라이선스가 하나라도 있으면 **🚨 CRITICAL로 보고**: GPL, AGPL, LGPL, MPL, SSPL, EUPL, CC-BY-SA, "UNKNOWN"
- UNKNOWN은 PyPI 메타데이터 누락일 수 있으니 해당 패키지의 GitHub 저장소 LICENSE를 직접 확인해 판정하라.

## 2. Node 의존성 스캔 (frontend 디렉토리가 있으면)
```bash
npx license-checker --production --summary
npx license-checker --production --onlyAllow "MIT;Apache-2.0;BSD-2-Clause;BSD-3-Clause;ISC;0BSD;CC0-1.0;Unlicense;Python-2.0"
```
- `--onlyAllow`가 실패하면 실패한 패키지와 라이선스를 명시해 보고하라.

## 3. SPDX 헤더 검증
```bash
reuse lint
```
- 헤더 누락 파일이 있으면 파일 목록을 출력하고, **자동으로 수정하지 말고** 누락 목록만 보고하라 (바이너리·생성 파일은 `.reuse/dep5` 처리 대상일 수 있음).

## 4. 금지 코드 혼입 검사
- `grep -ri "trufflehog" --include="*.py" --include="*.ts" --include="*.tsx" .` 로 TruffleHog(AGPL-3.0) 코드/패턴 포팅 흔적이 없는지 확인.
- Gitleaks 패턴을 참고한 파일이 있다면 `THIRD-PARTY-NOTICES.md`에 해당 출처가 기록되어 있는지 대조하라. 기록이 없으면 누락으로 보고.

## 5. AI 모델 가중치 라이선스 (해당 시)
- 프로젝트가 OCR 사전학습 모델 등 **모델 가중치 파일**을 포함/다운로드한다면, 코드 라이선스와 별개로 가중치 자체의 라이선스를 확인해 SBOM 기재 대상으로 보고하라. (예: PaddleOCR 코드는 Apache-2.0이지만 모델 파일은 별도 확인 필요)

## 최종 출력 형식
| 검사 항목 | 결과 | 조치 필요 사항 |
|---|---|---|
| Python 카피레프트 | ✅/🚨 | ... |
| Node 카피레프트 | ✅/🚨 | ... |
| SPDX 헤더 | ✅/🚨 | 누락 N건 |
| AGPL 혼입 | ✅/🚨 | ... |
| THIRD-PARTY-NOTICES 정합성 | ✅/🚨 | ... |
| 모델 가중치 라이선스 | ✅/⚠️/해당없음 | ... |
