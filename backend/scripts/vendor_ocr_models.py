# SPDX-FileCopyrightText: 2026 [Your Name]
# SPDX-License-Identifier: MIT
"""RapidOCR 한국어 인식 모델을 로컬로 벤더링한다 (재현성 — 런타임 다운로드 제거).

- 감지(det)·각도분류(cls) 모델은 `rapidocr` pip 패키지에 이미 번들되어 있어 별도 벤더링이
  필요 없다(패키지 버전 고정 = 자산 고정).
- 한국어 인식(rec) 모델만 별도 다운로드 대상이다(RapidOCR 저장소, Apache-2.0).

app/ocr.py 의 predev 격인 역할 — 백엔드 첫 실행 전(또는 CI에서) 한 번 실행한다. 이미 있고
해시가 맞으면 건너뛴다(오프라인 재실행 가능). 출처·라이선스: THIRD-PARTY-NOTICES.md 참고.
"""
from __future__ import annotations

import hashlib
import sys
import urllib.request
from pathlib import Path

MODEL_URL = (
    "https://www.modelscope.cn/models/RapidAI/RapidOCR/resolve/"
    "v3.9.2/onnx/PP-OCRv5/rec/korean_PP-OCRv5_rec_mobile.onnx"
)
SHA256 = "cd6e2ea50f6943ca7271eb8c56a877a5a90720b7047fe9c41a2e541a25773c9b"
DEST = Path(__file__).resolve().parent.parent / "app" / "ocr_models" / "korean_PP-OCRv5_rec_mobile.onnx"


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def main() -> None:
    if DEST.exists() and _sha256(DEST) == SHA256:
        print(f"[vendor-ocr] 이미 있음(해시 일치) — 건너뜀: {DEST}")
        return

    DEST.parent.mkdir(parents=True, exist_ok=True)
    print(f"[vendor-ocr] 다운로드 중… {MODEL_URL}")
    tmp = DEST.with_suffix(".onnx.tmp")
    try:
        urllib.request.urlretrieve(MODEL_URL, tmp)
    except OSError as e:
        print(f"[vendor-ocr] 다운로드 실패 — 네트워크 확인: {e}", file=sys.stderr)
        sys.exit(1)

    digest = _sha256(tmp)
    if digest != SHA256:
        tmp.unlink(missing_ok=True)
        print(f"[vendor-ocr] 해시 불일치(기대 {SHA256}, 실제 {digest}) — 손상된 다운로드", file=sys.stderr)
        sys.exit(1)

    tmp.replace(DEST)
    print(f"[vendor-ocr] 완료 → {DEST}")


if __name__ == "__main__":
    main()
