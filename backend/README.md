<!--
SPDX-FileCopyrightText: 2026 [Your Name]
SPDX-License-Identifier: MIT
-->

# KeyLens — 백엔드 (FastAPI, 로컬)

로컬 우선 백엔드. 사용자 기기에서만 돌며 외부로 데이터를 보내지 않는다.
현재 스프린트(S1) 범위: **지식베이스 로드 + Stage1 값 기반 분류**.
(OCR·Stage2 맥락 분류·암호화 저장은 후속 — `app/classify/pipeline.py`에 자리를 비워둠.)

## 실행

```bash
cd backend
python -m venv .venv
# Windows:  .venv\Scripts\activate     |  macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
python scripts/vendor_ocr_models.py   # 스크린샷 OCR용 한국어 인식 모델 로컬 벤더링(최초 1회)
uvicorn app.main:app --port 8003
```

## 테스트

```bash
pip install -r requirements-dev.txt
pytest
```

## 엔드포인트

| 메서드 | 경로 | 설명 |
|---|---|---|
| GET | `/health` | 상태 + 지식베이스 통계 |
| GET | `/knowledge` | 서비스·종류·변수명 (프론트가 종류 맵 구성용) |
| POST | `/analyze` | `{text?, url?}` → 분류 결과 목록 |
| POST | `/analyze/image` | 스크린샷(multipart `image`, 선택 `url`/`text`) → 로컬 OCR(RapidOCR, 한국어 인식) 후 분류 결과 목록 |

스모크:

```bash
curl -s http://localhost:8003/health
curl -s -X POST http://localhost:8003/analyze -H "Content-Type: application/json" \
  -d '{"text":"OPENAI_API_KEY=sk-proj-xxxxxxxxxxxxxxxxxxxx"}'
```

## 구조

```
app/
  main.py                FastAPI 앱 + 라우트 (+ 로컬 프론트 CORS)
  models.py              pydantic 스키마 (지식베이스 + API)
  knowledge.py           knowledge/*.yaml 로더·검증·정규식 컴파일
  masking.py             값 마스킹
  ocr.py                 스크린샷 OCR(RapidOCR, 한국어 인식 모델) — 이미지 → 라인 보존 텍스트
  ocr_models/            벤더링된 OCR 모델(.gitignore, scripts/vendor_ocr_models.py 로 재생성)
  classify/
    stage1.py            값 기반 분류 (접두어 정규식). 애매하면 unknown 안전분류
    stage2.py            맥락 기반 분류 (라벨·URL 신호) — 원본 컨텍스트/근처 URL·코드도 meta에 기록
    pipeline.py          Stage1+Stage2 병합·meta 보강
scripts/
  vendor_ocr_models.py   OCR 한국어 인식 모델 로컬 벤더링(해시 검증, 오프라인 재실행 가능)
knowledge/*.yaml         서비스 지식베이스 (파일 1개 = 서비스 1개, 코드 수정 0)
tests/                   pytest — 지식베이스·Stage1/2·API·OCR 회귀
```

## 분류 원칙 (SPEC 4.2 / 4.3)

- **Stage1(값 기반)**: `sk-`(OpenAI) · `AIza`(Google) · `secret_`/`ntn_`(Notion) 등 접두어가 명확한 키, 또는 `<32hex>.<24base62>`(Ollama)처럼 구조가 독특한 포맷을 `value_regex`로 즉시 식별(신뢰도 high).
- **애매한 값은 단정하지 않는다**: 노션의 database/data_source/page ID(동일 UUID)와 카카오 4종 키(동일 32 hex)는 `value_regex`가 없어 `unknown`으로 분류되고 Stage2(라벨·URL 맥락)로 넘어간다 — 이것이 KeyLens의 차별점.

## 라이선스 주의

`httpx`(FastAPI TestClient)는 `certifi`(**MPL-2.0**)를 끌어오므로 **의도적으로 쓰지 않는다**
(CLAUDE.md: 강한 카피레프트 금지 원칙 — 이 경우는 대체 가능한 선택지가 있어 그냥 회피). API 테스트는
라우트 함수를 직접 호출한다.

스크린샷 OCR(`app/ocr.py`, CORE-3)은 `rapidocr`(Apache-2.0)을 쓰며, 그 전이 의존성에 약한 카피레프트
2건(`tqdm`=MPL-2.0, `opencv-python`=LGPL-2.1 FFmpeg 플러그인 DLL)이 있다 — 둘 다 **수정 없이 그대로
사용 + 재링크/비전염 조건 충족**을 확인해 의도적으로 포함했다. 근거는 [THIRD-PARTY-NOTICES.md](../THIRD-PARTY-NOTICES.md) 참고.
그 외 의존성은 MIT/BSD/Apache/PSF.
