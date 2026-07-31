<!--
SPDX-FileCopyrightText: 2026 [Your Name]
SPDX-License-Identifier: MIT
-->
# 변경 이력 (Changelog)

이 프로젝트의 주요 변경을 기록합니다. 형식은 [Keep a Changelog](https://keepachangelog.com/ko/1.1.0/)를,
버전은 [유의적 버전(SemVer)](https://semver.org/lang/ko/)을 따릅니다.

## [Unreleased]

## [0.1.1] - 2026-07-31

### Added (기능)
- **직접 입력 탭**: 새 자격증명 분석 화면에 "직접 입력" 모드 추가. `NAME=VALUE` 붙여넣고
  Enter를 누르면 이름·값 두 칸으로 즉시 분리되고, 지식베이스와 정확히 일치하는 이름이면
  서비스·노출등급을 참고로 보여준다. 이름 칸은 cmd 스타일 Tab 자동완성(고스트 텍스트 +
  후보 순환)을 지원하고, 값을 채우면 새 행이 자동으로 추가된다.

### Fixed (수정)
- 자동 분류 결과가 "값만으로 판별 불가"만 있고 정상 결과가 하나도 없을 때 뒤로 갈 방법이
  없던 문제 — 해당 카드에 "새로 분석" 버튼을 추가하고, 사이드바 홈 탭(분석·입력)을 눌러도
  항상 빠져나올 수 있게 했다.

## [0.1.0] - 2026-07-30

첫 데스크톱 exe 릴리스. 아래는 지금까지 축적된 기능·변경 요약입니다.

### Added (기능)
- **분류 엔진**: 값 기반(Stage1)·**맥락 기반(Stage2, 차별점)** 2단계 분류 — 라벨·URL 신호로
  같은 형식의 애매한 키(Notion UUID류)를 판별, 신호 충돌 시 단정 없이 "확인 필요".
- **브라우저 OCR(CORE-3)**: tesseract.js로 스크린샷 → 라벨-값 페어링(이미지가 기기를 떠나지 않음),
  값 전용 정밀 재인식(bbox 크롭 + PSM + charset) + 신뢰도 플래깅.
- **암호화 금고(VAULT-1/2)**: Argon2id 키 유도 + 항목별 AES-256-GCM, SQLite에 암호문만 저장.
  세션 인증·자동 잠금·연속 실패 지연·감사 이력·키 회전(값 교체).
- **지식베이스**: 서비스별 키 종류·라벨·URL·변수명을 YAML로 선언(현재 9종:
  Notion·Kakao·GCP·OpenAI·Ollama·GitHub·AWS·Slack·Stripe). **YAML 하나로 백엔드·프론트 자동 반영**.
- **TRUST-1**: 사용자 트리거 시 서비스 read-only 엔드포인트로 1회 호출해 키 유효성(active/invalid/unknown) 확인.
- **TRUST-2**: 만료일 수동 입력 + JWT `exp` 자동 추출 + 임박 항목 상단 정렬.
- **SYNC-0**: 암호화 금고 번들 내보내기/가져오기(교체·병합) — 서버 없는 멀티 기기(제로 널리지).
- **CORE-5**: `.env` 내보내기(복사·다운로드·그룹별).
- **데스크톱 앱**: PyWebView 네이티브 창(`desktop/app.py`) + cx_Freeze 단일 실행 파일 패키징.
- **제출물**: 결과보고서·SBOM(붙임1)·AI 모델 활용 명세서(붙임2)·데모 스토리보드.

### Changed (변경)
- 프론트 서비스 종류맵을 하드코딩에서 **`/knowledge` 런타임 동적 구성**으로 전환(확장성 실체화).
- 의존성 상향: `fastapi` 0.115.6→0.139.0, `starlette` 0.41.3→1.3.1, `pytest` 8.3.4→9.0.3.

### Fixed (수정)
- OCR 값 재구성(구두점 분리 토큰 재결합), 프론트 에러 처리 하드닝(ErrorBoundary·친절 메시지),
  엣지 입력 무크래시, 허위 보안 표시 제거.

### Security (보안)
- 유출됐던 실제 테스트 키를 히스토리에서 완전 제거하고 `data/` 를 `.gitignore` 에 추가.
- 라이선스 카피레프트 0건(reuse lint 통과·SBOM), 의존성 취약점(SCA) 전 영역 0건(pip-audit·npm audit).
- 마스킹 노출 축소·감사 이력·잠금 정책 등 [SECURITY_REVIEW.md](./SECURITY_REVIEW.md) 항목 해소.

[Unreleased]: https://github.com/ttogle918/key-manager/compare/v0.1.1...main
[0.1.1]: https://github.com/ttogle918/key-manager/compare/v0.1.0...v0.1.1
[0.1.0]: https://github.com/ttogle918/key-manager/releases/tag/v0.1.0
