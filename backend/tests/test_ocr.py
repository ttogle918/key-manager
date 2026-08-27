# SPDX-FileCopyrightText: 2026 [Your Name]
# SPDX-License-Identifier: MIT
"""OCR 줄 단위 박스 좌표 보존(화면 설명 기능용) — 실제 데모 스크린샷으로 검증.

한국어 인식 모델이 로컬에 벤더링돼 있지 않으면 스킵한다
(test_ocr_demo_screenshots.py 와 동일 관례 — CI는 벤더링 후 실행하므로 실제로 돈다).
"""
from pathlib import Path

import pytest

from app.ocr import _KOREAN_REC_MODEL, run_ocr, run_ocr_lines

DEMO_DIR = Path(__file__).parent.parent.parent / "docs" / "demo"

pytestmark = pytest.mark.skipif(
    not _KOREAN_REC_MODEL.exists(),
    reason="OCR 모델 미벤더링 — python backend/scripts/vendor_ocr_models.py 먼저 실행",
)


def test_run_ocr_lines_returns_text_and_box_per_line():
    image_bytes = (DEMO_DIR / "notion.png").read_bytes()
    lines = run_ocr_lines(image_bytes)
    assert len(lines) > 0
    for line in lines:
        assert isinstance(line["text"], str) and line["text"]
        assert len(line["box"]) == 4  # 4점 폴리곤
        for point in line["box"]:
            assert len(point) == 2
            x, y = point
            assert isinstance(x, float) and isinstance(y, float)
            assert x >= 0 and y >= 0


def test_run_ocr_lines_filters_noise_words():
    image_bytes = (DEMO_DIR / "notion.png").read_bytes()
    lines = run_ocr_lines(image_bytes)
    texts_lower = {line["text"].strip().lower() for line in lines}
    assert not (texts_lower & {"copy", "복사", "show", "표시"})


def test_run_ocr_lines_matches_run_ocr_joined_text():
    """리팩터링 회귀 확인 — run_ocr()의 줄바꿈 조인 결과와 정확히 같아야 한다."""
    image_bytes = (DEMO_DIR / "notion.png").read_bytes()
    joined = run_ocr(image_bytes)
    lines = run_ocr_lines(image_bytes)
    assert joined == "\n".join(line["text"] for line in lines)


def test_run_ocr_lines_empty_image_like_input_returns_empty_list():
    """1x1 흰 픽셀 PNG(텍스트 없음) — 빈 리스트를 반환해야 한다(예외 없이)."""
    import base64

    tiny_png = base64.b64decode(
        "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII="
    )
    assert run_ocr_lines(tiny_png) == []
