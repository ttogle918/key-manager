<!--
SPDX-FileCopyrightText: 2026 [Your Name]
SPDX-License-Identifier: MIT
-->
# 데모/테스트 스크린샷 세트 (DEMO-1)

각 서비스 콘솔 화면을 **더미 값**으로 재현한 스크린샷이다. CORE-3(OCR)·OSS-4(데모 영상)가 공유하고,
루트 `README.md`와 프론트 입력 화면(“스크린샷을 던져보세요”)에서 참조한다.

> ⚠️ **전부 가짜 값(placeholder)이다.** 실제 발급 키를 캡처하지 않는다(CLAUDE.md 시크릿 위생).
> 값 형식만 지식베이스 정규식에 맞춰 “진짜처럼” 보이게 했을 뿐, 어떤 서비스에서도 유효하지 않다.

## 이미지와 기대 분류(ground-truth)

| 파일 | 화면 | 담긴 라벨·값 | 기대 official_env_name |
|---|---|---|---|
| `notion.png` | Notion 통합 설정 | Internal Integration Secret(값기반) · Database ID(Stage2 라벨) | `NOTION_API_KEY`, `NOTION_DATABASE_ID` |
| `kakao.png` | Kakao Developers 앱 키 | REST API 키 · JavaScript 키 · Admin 키 · Native 앱 키 (32hex ×4) | `KAKAO_REST_API_KEY`, `KAKAO_JS_KEY`, `KAKAO_ADMIN_KEY`, `KAKAO_NATIVE_APP_KEY` |
| `gcp.png` | Google Cloud 사용자 인증 정보 | API 키(`AIza…`) | `GOOGLE_API_KEY` |
| `openai.png` | OpenAI API keys | Secret key(`sk-…`) · Organization ID(`org-…`) | `OPENAI_API_KEY`, `OPENAI_ORG_ID` |
| `github.png` | GitHub Personal access tokens | Token (classic)(`ghp_…`, 값기반) | `GITHUB_TOKEN` |
| `aws.png` | AWS IAM 사용자 자격 증명 | Access key ID(값기반 `AKIA…`) · Secret access key(라벨 전용, 값규칙 없음) | `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY` |
| `slack.png` | Slack OAuth & Permissions | Bot User OAuth Token(`xoxb-…`) · User OAuth Token(`xoxp-…`) | `SLACK_BOT_TOKEN`, `SLACK_USER_TOKEN` |
| `stripe.png` | Stripe Developers API keys | Secret key(`sk_test_…`) · Publishable key(`pk_test_…`) | `STRIPE_SECRET_KEY`, `STRIPE_PUBLISHABLE_KEY` |

> `github`/`aws`/`slack`/`stripe` 4종은 백엔드 OCR(RapidOCR, 아래 절) 검증 전용으로 추가했다 —
> `notion`/`kakao`/`gcp`/`openai` 4종처럼 브라우저 tesseract.js 골든 픽스처(`*.recon.txt`)는 없다.

## OCR 회귀 픽스처

브라우저 OCR(tesseract.js)은 결정적이지만 파이썬에서 재현할 수 없어, **OCR 재구성 결과를 골든 텍스트로 커밋**한다:
`backend/tests/fixtures/demo/*.recon.txt` → `backend/tests/test_demo_fixtures.py`가 분류 계약을 검증한다.

현재 엔진 기준 **7/9** env 를 분류한다. `kakao.png`의 **JavaScript 키·Native 앱 키**는 한글 단일 글자
(“키”→“7|”, “앱”→“&”) OCR 오독으로 라벨 매칭에 실패한다 — 알려진 한계이며 CORE-3 전처리(대비·확대) 후속에서
개선한다. REST API 키·Admin 키는 한글 라벨이 정확히 인식되어, 한글 OCR 자체는 동작함을 보인다.

## 재생성

```bash
pip install Pillow                 # 개발 전용(런타임 의존성 아님)
python docs/demo/generate.py       # docs/demo/*.png 재생성 (전부 더미)
python docs/demo/make_gif.py       # docs/demo/demo.gif 재생성 (README 히어로)
# 이어서 프론트에서 OCR 재실행 → backend/tests/fixtures/demo/*.recon.txt 갱신
# (tesseract.js 버전/언어데이터가 바뀌면 골든 텍스트도 갱신 필요)
```

## README 히어로 GIF (`demo.gif`)

`make_gif.py`가 **콘솔 스크린샷 → 분류 결과** magic moment 를 앱 다크 테마로 렌더링한다(정지 프레임 3장,
루프). 입력은 실제 더미 스크린샷(`notion.png`), 결과 카드는 그 화면의 분류 결과(값 없이 종류·변수명만)다.
같은 32자 UUID 형식을 **맥락(라벨)으로 API Key vs Database ID 로 구분**하는 차별점을 한눈에 보여준다.

> 이 GIF 는 정지 자산으로 만든 예시다. **실제 앱 화면 시연 영상**은 OSS-4(3분 데모)에서 별도 녹화한다.

## 실제 앱 기능 워크스루 GIF (`feature-walkthrough.gif`)

실제 브라우저에서 앱을 조작하며 캡처한 라이브 녹화본이다(2026-08-25). 더미 값으로 마스터 비밀번호 설정 →
텍스트·URL 분석(맥락 기반 분류) → 결과 저장 → 보관함 대시보드 → 값 복호화(공개) → `.env` 내보내기 →
금고 파일 내보내기(SYNC-0) → 잠금까지 전체 흐름을 담았다. `demo.gif`(정지 자산)와 달리 실제 UI 상호작용을
그대로 기록한 것이라 기능이 실제로 동작함을 보여주는 용도다.
