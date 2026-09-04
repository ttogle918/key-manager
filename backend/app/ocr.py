# SPDX-FileCopyrightText: 2026 [Your Name]
# SPDX-License-Identifier: MIT
"""스크린샷 OCR — RapidOCR(한국어 PP-OCRv5 인식 모델, Apache-2.0)으로 이미지 → 라인 보존 텍스트.

CORE-3 원안(tesseract.js, 브라우저 클라이언트)은 한글 단일 글자 라벨("키"/"앱")을 반복적으로
오독했다(예: Kakao JS/Native 키). RapidOCR 한국어 인식 모델로 교체 실험 결과 같은 케이스를
전부 정확히 인식해 이 백엔드 경로로 옮긴다 — 로컬 백엔드(127.0.0.1)에서만 처리하므로
"이 기기 안에서만 분석"이라는 로컬 우선 원칙과 대회 규정 제9조(로컬 구동 필수)는 그대로 유지된다.

Stage2(`classify_context`)가 "값이 있는 줄 + 바로 위 줄"을 라벨 컨텍스트로 쓰므로,
검출된 텍스트 줄을 위→아래(같은 높이면 왼→오)로 정렬해 줄바꿈으로 이어붙여 반환한다.
"""
from __future__ import annotations

import logging
from pathlib import Path
from threading import Lock

from rapidocr import RapidOCR
from rapidocr.utils.typings import LangRec, ModelType, OCRVersion

logging.getLogger("RapidOCR").setLevel(logging.WARNING)

_KOREAN_REC_MODEL = Path(__file__).resolve().parent / "ocr_models" / "korean_PP-OCRv5_rec_mobile.onnx"

# 콘솔 UI 잡음(복사/표시 버튼 등) — 라벨·값이 아니므로 재구성 텍스트에서 제외한다.
# 기준: 값도 라벨도 아닌 조작 버튼 텍스트. 원래 브라우저 OCR(tesseract.js) 경로에서 쓰던
# 목록을 그대로 옮겨왔고, 그 경로는 2026-09-04 에 제거됐다(dist 44MB 감축).
_NOISE_LINES = {
    "copy", "copied", "복사", "복사됨", "show", "hide", "표시", "숨기기",
    "reveal", "regenerate", "재발급", "refresh", "reset", "edit", "delete", "삭제",
}

_engine: RapidOCR | None = None
_engine_lock = Lock()


class OcrUnavailableError(RuntimeError):
    """한국어 인식 모델이 벤더링되지 않았을 때(README 안내: vendor_ocr_models.py 먼저 실행)."""


def _get_engine() -> RapidOCR:
    global _engine
    if _engine is not None:
        return _engine
    with _engine_lock:
        if _engine is None:
            if not _KOREAN_REC_MODEL.exists():
                raise OcrUnavailableError(
                    "OCR 모델이 없습니다 - "
                    "`python backend/scripts/vendor_ocr_models.py` 를 먼저 실행하세요."
                )
            _engine = RapidOCR(
                params={
                    "Rec.lang_type": LangRec.KOREAN,
                    "Rec.ocr_version": OCRVersion.PPOCRV5,
                    "Rec.model_type": ModelType.MOBILE,
                    "Rec.model_path": str(_KOREAN_REC_MODEL),
                }
            )
    return _engine


def _line_key(box) -> tuple[float, float]:
    """4점 폴리곤 박스를 (세로 중심, 가로 중심)으로 — 위→아래, 왼→오 정렬용."""
    ys = [p[1] for p in box]
    xs = [p[0] for p in box]
    return (sum(ys) / len(ys), sum(xs) / len(xs))


def _recognize_lines(image_bytes: bytes) -> list[tuple[list, str]]:
    """이미지 → (박스, 텍스트) 줄 목록. 위→아래, 왼→오 정렬, 노이즈 줄 제외."""
    engine = _get_engine()
    result = engine(image_bytes)
    if result is None or result.boxes is None or len(result.boxes) == 0:
        return []

    rows = sorted(zip(result.boxes, result.txts), key=lambda r: _line_key(r[0]))

    lines: list[tuple[list, str]] = []
    for box, txt in rows:
        t = txt.strip()
        if not t or t.lower() in _NOISE_LINES:
            continue
        lines.append((box, t))
    return lines


def run_ocr(image_bytes: bytes) -> str:
    """이미지 바이트 → 줄 순서 보존 텍스트. 검출 결과가 없으면 빈 문자열."""
    lines = _recognize_lines(image_bytes)
    return "\n".join(t for _box, t in lines)


def run_ocr_lines(image_bytes: bytes) -> list[dict]:
    """이미지 바이트 → 줄 단위 {text, box} 목록(화면 설명 기능용 — 박스 좌표 보존).

    box는 4점 폴리곤 [[x,y],[x,y],[x,y],[x,y]](RapidOCR 원본 좌표, 이미지 픽셀 단위).
    """
    lines = _recognize_lines(image_bytes)
    return [
        {"text": t, "box": [[float(x), float(y)] for x, y in box]}
        for box, t in lines
    ]
