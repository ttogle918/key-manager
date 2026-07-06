# SPDX-FileCopyrightText: 2026 [Your Name]
# SPDX-License-Identifier: MIT
"""README 히어로용 데모 GIF 생성 (개발 전용).

"콘솔 스크린샷을 던지면 → KeyLens가 무슨 키인지 가려 공식 변수명으로 매핑" 이라는
magic moment 를 앱 다크 테마로 렌더링한다. 입력은 실제 더미 데모 스크린샷(docs/demo/notion.png),
출력 카드는 그 스크린샷의 분류 결과(더미)다. **모든 값은 가짜.**

실행: backend venv 로 `python docs/demo/make_gif.py`  → docs/demo/demo.gif
※ 실제 앱 화면 녹화(screencast)는 OSS-4(영상)에서 별도 진행. 이 GIF 는 정지 자산으로 만든 예시.
"""
from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

HERE = Path(__file__).resolve().parent

# 앱 다크 테마(frontend/src/index.css 와 일치)
BG = "#0b0d10"
PANEL = "#101318"
PANEL_HEAD = "#13161b"
BORDER = "#232931"
LINE = "#1b2027"
FG = "#e7eaee"
FG_SOFT = "#c7cdd6"
MUTED = "#98a1ae"
DIM = "#6b7482"
MINT = "#3ecf8e"
MINT_SOFT = "#5fd9a4"
BADGE_BG = "#14281e"

SANS = [r"C:\Windows\Fonts\malgun.ttf", r"C:\Windows\Fonts\segoeui.ttf", r"C:\Windows\Fonts\arial.ttf"]
SANS_BD = [r"C:\Windows\Fonts\malgunbd.ttf", r"C:\Windows\Fonts\segoeuib.ttf", r"C:\Windows\Fonts\arialbd.ttf"]
MONO = [r"C:\Windows\Fonts\consola.ttf", r"C:\Windows\Fonts\cour.ttf"]


def font(paths: list[str], size: int) -> ImageFont.FreeTypeFont:
    for p in paths:
        if Path(p).exists():
            return ImageFont.truetype(p, size)
    return ImageFont.load_default(size)


W, H = 1120, 470
f_tag = font(SANS_BD, 22)
f_sub = font(SANS, 14)
f_cap = font(SANS, 14)
f_type = font(SANS_BD, 16)
f_env = font(MONO, 15)
f_badge = font(SANS_BD, 12)
f_tile = font(SANS_BD, 15)
f_small = font(SANS, 12)

# 입력 스크린샷(실제 더미 데모 자산)
shot = Image.open(HERE / "notion.png").convert("RGB")
sw = 500
shot = shot.resize((sw, round(shot.height * sw / shot.width)), Image.LANCZOS)

# 결과 카드(위 스크린샷의 분류 결과 — 값은 없고 종류·변수명만) — 같은 UUID 형식을 맥락으로 구분한 차별점
CARDS = [
    ("N", "#E7EAEE", "#15181D", "API Key", "NOTION_API_KEY"),
    ("N", "#E7EAEE", "#15181D", "Database ID", "NOTION_DATABASE_ID"),
]

PANEL_X, PANEL_Y, PANEL_W, PANEL_H = 630, 108, 452, 300


def rr(d, box, r, **kw):
    d.rounded_rectangle(box, radius=r, **kw)


def base_frame() -> Image.Image:
    im = Image.new("RGB", (W, H), BG)
    d = ImageDraw.Draw(im)
    # 상단 타이틀
    d.text((40, 22), "KeyLens — 스크린샷을 던지면 무슨 키인지 가려 공식 변수명으로 매핑", font=f_tag, fill=FG)
    d.text((40, 55), "값이 아니라 화면 속 라벨·URL 맥락으로 분류 · 로컬에 암호화 보관", font=f_sub, fill=MUTED)
    # ① 입력
    d.text((40, 84), "①  콘솔 스크린샷", font=f_cap, fill=DIM)
    ix, iy = 40, 112
    rr(d, [ix - 2, iy - 2, ix + sw + 2, iy + shot.height + 2], 10, outline=BORDER, width=2)
    im.paste(shot, (ix, iy))
    # 화살표
    d.text((565, 190), "→", font=font(SANS_BD, 40), fill=MINT)
    # ② 결과 패널
    d.text((PANEL_X, 84), "②  자동 분류 → 공식 변수명", font=f_cap, fill=DIM)
    rr(d, [PANEL_X, PANEL_Y, PANEL_X + PANEL_W, PANEL_Y + PANEL_H], 12, fill=PANEL, outline=BORDER, width=1)
    rr(d, [PANEL_X, PANEL_Y, PANEL_X + PANEL_W, PANEL_Y + 40], 12, fill=PANEL_HEAD)
    d.rectangle([PANEL_X, PANEL_Y + 28, PANEL_X + PANEL_W, PANEL_Y + 40], fill=PANEL_HEAD)
    d.text((PANEL_X + 16, PANEL_Y + 12), "Notion  ·  분류 결과", font=f_small, fill=MUTED)
    d.line([PANEL_X, PANEL_Y + 40, PANEL_X + PANEL_W, PANEL_Y + 40], fill=LINE, width=1)
    # 하단 태그
    d.text((W - 200, H - 26), "데모 · 모든 값은 더미", font=f_small, fill=DIM)
    return im


def draw_card(d: ImageDraw.ImageDraw, idx: int) -> None:
    tile, tbg, tfg, typ, env = CARDS[idx]
    x = PANEL_X + 16
    y = PANEL_Y + 54 + idx * 62
    # 서비스 타일
    rr(d, [x, y + 6, x + 32, y + 38], 7, fill=tbg)
    tw = d.textlength(tile, font=f_tile)
    d.text((x + 16 - tw / 2, y + 12), tile, font=f_tile, fill=tfg)
    # 종류 + 변수명
    tx = x + 44
    d.text((tx, y + 6), typ, font=f_type, fill=FG_SOFT)
    d.text((tx, y + 28), env, font=f_env, fill=MINT_SOFT)
    # 신뢰도 뱃지
    label = "신뢰도 높음"
    bw = d.textlength(label, font=f_badge) + 18
    bx = PANEL_X + PANEL_W - 16 - bw
    rr(d, [bx, y + 12, bx + bw, y + 34], 6, fill=BADGE_BG, outline="#2c5c44", width=1)
    d.text((bx + 9, y + 16), label, font=f_badge, fill=MINT_SOFT)


def _frame(n_cards: int, analyzing: bool = False) -> Image.Image:
    im = base_frame()
    d = ImageDraw.Draw(im)
    if analyzing:
        d.text((PANEL_X + 16, PANEL_Y + 60), "분석 중…", font=f_type, fill=DIM)
    for i in range(n_cards):
        draw_card(d, i)
    return im


def build() -> None:
    # 3개 distinct 프레임: 분석 중 → 카드1 → 카드2(홀드 길게). 루프 반복.
    frames = [_frame(0, analyzing=True), _frame(1), _frame(2)]
    durations = [850, 480, 2600]  # 프레임별 ms
    pal = [f.convert("P", palette=Image.ADAPTIVE, colors=128) for f in frames]
    out = HERE / "demo.gif"
    pal[0].save(
        out, save_all=True, append_images=pal[1:], duration=durations,
        loop=0, optimize=True, disposal=2,
    )
    print("wrote", out, f"({out.stat().st_size // 1024} KB, {len(frames)} frames)")


if __name__ == "__main__":
    build()
