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
  classify/
    stage1.py            값 기반 분류 (접두어 정규식). 애매하면 unknown 안전분류
    pipeline.py          파이프라인 (Stage2·OCR 연결 지점)
knowledge/*.yaml         서비스 지식베이스 (파일 1개 = 서비스 1개, 코드 수정 0)
tests/                   pytest — 지식베이스·Stage1·API
```

## 분류 원칙 (SPEC 4.2 / 4.3)

- **Stage1(값 기반)**: `sk-`(OpenAI) · `AIza`(Google) · `secret_`/`ntn_`(Notion) 등 접두어가 명확한 키를 `value_regex`로 즉시 식별(신뢰도 high).
- **애매한 값은 단정하지 않는다**: 노션의 database/data_source/page ID(동일 UUID)와 카카오 4종 키(동일 32 hex)는 `value_regex`가 없어 `unknown`으로 분류되고 Stage2(라벨·URL 맥락)로 넘어간다 — 이것이 KeyLens의 차별점.

## 라이선스 주의

`httpx`(FastAPI TestClient)는 `certifi`(**MPL-2.0**)를 끌어오므로 **의도적으로 쓰지 않는다**
(CLAUDE.md: 카피레프트 금지). API 테스트는 라우트 함수를 직접 호출한다. 전체 의존성은 MIT/BSD/Apache/PSF만.
