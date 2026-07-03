# SPDX-FileCopyrightText: 2026 [Your Name]
# SPDX-License-Identifier: MIT
"""KeyLens 로컬 백엔드 API.

로컬 우선(local-first): 이 서버는 사용자 기기에서만 돌며 외부로 데이터를 보내지 않는다.
현재 제공: 지식베이스 조회 + Stage1 값 기반 분석. (암호화 저장·OCR·Stage2 는 후속.)
"""
from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .classify.pipeline import analyze
from .knowledge import load_knowledge_base
from .models import AnalyzeRequest, AnalyzeResponse, HealthResponse

app = FastAPI(title="KeyLens API", version="0.1.0")

# 로컬 프론트엔드(Vite dev)만 허용.
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://localhost:5199",
        "http://127.0.0.1:5173",
        "http://127.0.0.1:5199",
    ],
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)

# 지식베이스는 기동 시 1회 로드 (검증 실패하면 서버가 뜨지 않는다).
KB = load_knowledge_base()


@app.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    return HealthResponse(
        status="ok", services=len(KB.services), credentials=KB.credential_count
    )


@app.get("/knowledge")
def knowledge() -> dict:
    """프론트가 종류·변수명 맵을 동적으로 구성할 수 있도록 지식베이스를 노출."""
    return {
        "services": [
            {
                "service": s.service,
                "display_name": s.display_name,
                "credentials": [
                    {
                        "kind": c.kind,
                        "label": c.label,
                        "official_env_name": c.official_env_name,
                        "value_based": c.value_regex is not None,
                        "expiry_known": c.expiry_known,
                    }
                    for c in s.credentials
                ],
            }
            for s in KB.services
        ]
    }


@app.post("/analyze", response_model=AnalyzeResponse)
def analyze_endpoint(request: AnalyzeRequest) -> AnalyzeResponse:
    return analyze(request, KB)


# 로컬 기본 포트 8003 (흔한 8000 회피). `python -m app.main` 으로 실행 가능.
DEFAULT_PORT = 8003

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="127.0.0.1", port=DEFAULT_PORT)
