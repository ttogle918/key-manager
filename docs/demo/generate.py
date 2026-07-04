# SPDX-FileCopyrightText: 2026 [Your Name]
# SPDX-License-Identifier: MIT
"""데모/OCR 회귀용 콘솔 스크린샷 생성기 (DEMO-1).

각 서비스 콘솔 화면을 **더미 값**으로 재현한다. 실제 키는 절대 쓰지 않는다(CLAUDE.md 시크릿 위생).
값은 모두 지식베이스(backend/knowledge/*.yaml)의 value_regex / label_patterns 와 맞춰
CORE-3(OCR) → CORE-2(Stage2) 분류가 실제로 걸리도록 설계했다.

개발 전용 도구 — 프로젝트 런타임 의존성 아님. 실행:  pip install Pillow && python docs/demo/generate.py
출력 PNG 와 ground-truth 는 저장소에 커밋되어 있어 이 스크립트를 다시 돌리지 않아도 된다.
"""
from __future__ import annotations

import re
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

OUT = Path(__file__).parent

# ── 더미 값 (전부 가짜, 정규식 검증됨) ─────────────────────────────────────────
# ⚠️ OCR 친화: 숫자 0·1 을 피한다(각각 O/@, l/I 로 오독됨). hex 는 [2-9a-f] 만 사용.
NOTION_SECRET = "secret_" + "abcdefghjkmnpqrstuvwxyzABCDEFGHJKMNPQRST"  # ^(secret_|ntn_)[A-Za-z0-9]{36,}$ (40)
NOTION_DB_ID = "3e9a2c4e7b4d4e8a9c5e2d5e8a7b4c3e"  # 32 hex → Stage2 라벨
# hex 인데 f 도 뺀다([2-9a-e]) — OCR 이 mono 'f' 를 'Ff' 로 중복 오독하는 사례 회피.
KAKAO_REST = "a2b3c4d5e6e7a8b9c2d3e4e5a6b7c8d9"
KAKAO_JS = "b3c4d5e6e7a8b9c2d3e4e5a6b7c8d9ea"
KAKAO_ADMIN = "c4d5e6e7a8b9c2d3e4e5a6b7c8d9eaeb"
KAKAO_NATIVE = "d5e6e7a8b9c2d3e4e5a6b7c8d9eaebac"
GCP_KEY = "AIza" + "SyDummyKeyTwoThreeFourFiveSixSevenAb"[:35]  # AIza + 35
OPENAI_SECRET = "sk-proj-" + "DummyTwoThreeAbcdEfghTwoThree"  # sk-(proj-)?[A-Za-z0-9_-]{20,}
OPENAI_ORG = "org-" + "DummyTwoThreeAbcdEfghXy"  # org-[A-Za-z0-9]{20,}

# 화면별 정의: (파일명, 헤더, [(라벨, 값, 값모노여부)], 기대 env)
SCREENS = [
    (
        "notion.png",
        "Notion · Integration settings",
        [
            ("Internal Integration Secret", NOTION_SECRET, True),
            ("Database ID", NOTION_DB_ID, True),
        ],
        ["NOTION_API_KEY", "NOTION_DATABASE_ID"],
    ),
    (
        "kakao.png",
        "Kakao Developers · 앱 키",
        [
            ("REST API 키", KAKAO_REST, True),
            ("JavaScript 키", KAKAO_JS, True),
            ("Admin 키", KAKAO_ADMIN, True),
            ("Native 앱 키", KAKAO_NATIVE, True),
        ],
        ["KAKAO_REST_API_KEY", "KAKAO_JS_KEY", "KAKAO_ADMIN_KEY", "KAKAO_NATIVE_APP_KEY"],
    ),
    (
        "gcp.png",
        "Google Cloud · API 및 서비스 · 사용자 인증 정보",
        [("API 키", GCP_KEY, True)],
        ["GOOGLE_API_KEY"],
    ),
    (
        "openai.png",
        "OpenAI · API keys",
        [
            ("Secret key", OPENAI_SECRET, True),
            ("Organization ID", OPENAI_ORG, True),
        ],
        ["OPENAI_API_KEY", "OPENAI_ORG_ID"],
    ),
]

# 색: 밝은 콘솔 테마 (OCR 대비 좋게)
BG = "#ffffff"
HEADER_BG = "#f3f4f6"
LABEL = "#5b6470"
VALUE = "#111418"
TITLE = "#1a1d21"
BTN = "#2563eb"
LINE = "#e3e6ea"


def _font(paths: list[str], size: int) -> ImageFont.FreeTypeFont:
    for p in paths:
        try:
            return ImageFont.truetype(p, size)
        except OSError:
            continue
    return ImageFont.load_default(size)


SANS = [r"C:\Windows\Fonts\malgun.ttf", r"C:\Windows\Fonts\segoeui.ttf", r"C:\Windows\Fonts\arial.ttf"]
# 라벨(특히 한글)은 볼드가 OCR 대비가 좋다 — "키/앱" 오독 감소.
SANS_BOLD = [r"C:\Windows\Fonts\malgunbd.ttf", r"C:\Windows\Fonts\segoeuib.ttf", r"C:\Windows\Fonts\arialbd.ttf"]
MONO = [r"C:\Windows\Fonts\consola.ttf", r"C:\Windows\Fonts\cour.ttf"]


def render(name: str, header: str, rows, _envs) -> None:
    f_title = _font(SANS, 26)
    f_label = _font(SANS_BOLD, 24)
    f_value = _font(MONO, 26)
    f_btn = _font(SANS, 17)

    W = 900
    pad = 44
    row_h = 96
    H = 150 + row_h * len(rows) + pad
    img = Image.new("RGB", (W, H), BG)
    d = ImageDraw.Draw(img)

    # 헤더 바
    d.rectangle([0, 0, W, 84], fill=HEADER_BG)
    d.line([0, 84, W, 84], fill=LINE, width=1)
    d.text((pad, 28), header, fill=TITLE, font=f_title)

    y = 122
    for label, value, mono in rows:
        d.text((pad, y), label, fill=LABEL, font=f_label)
        vf = f_value if mono else f_label
        d.text((pad, y + 30), value, fill=VALUE, font=vf)
        # 값 옆 '복사' 버튼(OCR 잡음 제거 대상)
        d.text((W - pad - 46, y + 32), "복사", fill=BTN, font=f_btn)
        d.line([pad, y + row_h - 18, W - pad, y + row_h - 18], fill=LINE, width=1)
        y += row_h

    img.save(OUT / name)
    print(f"  wrote {name}  ({W}x{H})")


def main() -> None:
    # 값이 지식베이스 정규식에 맞는지 사전 검증(가짜지만 형식은 진짜처럼).
    checks = [
        (NOTION_SECRET, r"^(secret_|ntn_)[A-Za-z0-9]{36,}$"),
        (GCP_KEY, r"^AIza[0-9A-Za-z_\-]{35}$"),
        (OPENAI_SECRET, r"^sk-(proj-)?[A-Za-z0-9_\-]{20,}$"),
        (OPENAI_ORG, r"^org-[A-Za-z0-9]{20,}$"),
    ]
    for val, pat in checks:
        assert re.match(pat, val), f"정규식 불일치: {val} !~ {pat}"
    for v in (NOTION_DB_ID, KAKAO_REST, KAKAO_JS, KAKAO_ADMIN, KAKAO_NATIVE):
        assert re.fullmatch(r"[0-9a-f]{32}", v), f"32hex 아님: {v}"

    print("데모 스크린샷 생성 (전부 더미 값):")
    for name, header, rows, envs in SCREENS:
        render(name, header, rows, envs)
    print("완료. 실제 키 아님 — OCR/분류 회귀 픽스처용.")


if __name__ == "__main__":
    main()
