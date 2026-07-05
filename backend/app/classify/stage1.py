# SPDX-FileCopyrightText: 2026 [Your Name]
# SPDX-License-Identifier: MIT
"""Stage 1 — 값 기반 분류 (SPEC 4.2).

접두사가 명확한 키를 지식베이스의 value_regex 로 즉시 식별한다.
값만으로 애매한 값(UUID·32 hex 등)은 절대 단정하지 않고 unknown 으로 안전 분류해
Stage 2(맥락 기반)로 넘긴다.
"""
from __future__ import annotations

import math
import re
from collections import Counter

from ..knowledge import KnowledgeBase
from ..masking import mask
from ..models import ClassifiedItem

# ── 정규식 ──
# NAME=VALUE / export NAME=VALUE / name: value  (값은 공백·따옴표·주석 전까지)
# group1=이름, group2=여는 따옴표(없으면 ''), group3=값. 여는 따옴표를 잡아 값 절단 판정에 쓴다.
_ASSIGN_RE = re.compile(
    r'^[ \t]*(?:export[ \t]+)?["\']?([A-Za-z_][\w.\-]*)["\']?[ \t]*[:=][ \t]*'
    r'(["\']?)([^"\'\s#]+)',
    re.MULTILINE,
)
_BARE_ASSIGN_RE = re.compile(r"^[A-Za-z_][\w.\-]*[:=](.+)$")
_UUID_RE = re.compile(
    r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$"
)
_HEX32_RE = re.compile(r"^[0-9a-fA-F]{32}$")
_STRIP_CHARS = "\"'`,;:()[]{}<>"

_PREFIX_HINTS = [
    ("sk-proj-", "sk-proj- 접두어"),
    ("sk-", "sk- 접두어"),
    ("AIza", "AIza 접두어"),
    ("secret_", "secret_ 접두어"),
    ("ntn_", "ntn_ 접두어"),
    ("org-", "org- 접두어"),
]


def _shannon_entropy(s: str) -> float:
    if not s:
        return 0.0
    n = len(s)
    return -sum((c / n) * math.log2(c / n) for c in Counter(s).values())


def _looks_secret(v: str) -> bool:
    """접두어 없이도 '자격증명처럼 보이는' 값인지 (unknown 포함 여부 판단)."""
    if _UUID_RE.match(v) or _HEX32_RE.match(v):
        return True
    if len(v) < 12:
        return False
    has_alpha = any(c.isalpha() for c in v)
    has_digit = any(c.isdigit() for c in v)
    return has_alpha and has_digit and _shannon_entropy(v) >= 3.0


def _format_hint(value: str) -> str:
    for prefix, hint in _PREFIX_HINTS:
        if value.startswith(prefix):
            return hint
    return "패턴 일치"


def _unknown_format(value: str) -> str:
    if _UUID_RE.match(value):
        return "UUID"
    if _HEX32_RE.match(value):
        return "32자리 hex"
    return f"{len(value)}자 문자열"


def _clean(tok: str) -> str:
    return tok.strip().strip(_STRIP_CHARS)


def extract_candidates(text: str) -> list[tuple[str, str, str | None, bool]]:
    """텍스트에서 (값, 출처, 대입변수명, 절단여부) 후보를 뽑는다. 값 기준 중복 제거.

    절단(truncated): NAME=VALUE 에서 값이 `#` 또는 (여는 것과 다른) 따옴표에서 잘렸을 때.
    잘린 불완전한 키가 그대로 저장되지 않도록 프론트에 경고 신호를 준다(SECURITY_REVIEW 5-3).
    """
    seen: set[str] = set()
    out: list[tuple[str, str, str | None, bool]] = []

    for m in _ASSIGN_RE.finditer(text):
        name, opening, value = m.group(1), m.group(2), _clean(m.group(3))
        stop = text[m.end() : m.end() + 1]  # 값을 멈추게 한 문자
        if stop == "#":
            truncated = True  # 주석 문자 앞에서 잘림(값의 일부일 수 있음)
        elif stop in ('"', "'"):
            truncated = stop != opening  # 여는 따옴표와 같으면 정상 종료, 다르면 잘림
        else:
            truncated = False  # 공백/EOL — 정상 종료
        if value and value not in seen:
            seen.add(value)
            out.append((value, "assignment", name, truncated))

    for raw in re.split(r"\s+", text):
        tok = _clean(raw)
        if not tok:
            continue
        bare = _BARE_ASSIGN_RE.match(tok)
        if bare:
            tok = _clean(bare.group(1))
        if tok and tok not in seen:
            seen.add(tok)
            out.append((tok, "token", None, False))

    return out


def classify_text(text: str, kb: KnowledgeBase, source_label: str = "text") -> list[ClassifiedItem]:
    """텍스트를 Stage1 로 분류한다."""
    items: list[ClassifiedItem] = []

    for value, origin, name, truncated in extract_candidates(text):
        matches = [vm for vm in kb.value_matchers if vm.pattern.match(value)]
        envs = {vm.credential.official_env_name for vm in matches}
        source = f"{source_label} · {'대입' if origin == 'assignment' else '토큰'}"

        if len(envs) == 1:
            vm = matches[0]
            meta: dict = {"detected_by": "value_regex"}
            if name:
                meta["assigned_name"] = name
            if truncated:
                meta["truncated"] = True
            items.append(
                ClassifiedItem(
                    value=value,
                    masked=mask(value),
                    service=vm.service.service,
                    display_name=vm.service.display_name,
                    kind=vm.credential.kind,
                    label=vm.credential.label,
                    official_env_name=vm.credential.official_env_name,
                    confidence="high",
                    format=_format_hint(value),
                    source=source,
                    stage=1,
                    meta=meta,
                )
            )
        elif len(envs) > 1:
            # 여러 서비스 규칙이 동시에 매치 — 단정 금지
            multi_meta: dict = {
                "candidates": sorted(envs),
                "note": "value_regex 다중 매치 — Stage2 필요",
            }
            if truncated:
                multi_meta["truncated"] = True
            items.append(
                ClassifiedItem(
                    value=value,
                    # 서비스 미확정 = 접두어가 공개 정보라는 보장 없음 → 노출 축소
                    masked=mask(value, keep_front=4),
                    kind="ambiguous",
                    label="종류 미확정",
                    confidence="unknown",
                    format=_format_hint(value),
                    source=source,
                    stage=1,
                    meta=multi_meta,
                )
            )
        elif origin == "assignment" or _looks_secret(value):
            meta = {"reason": "값 기반 미상 — Stage2(맥락) 필요"}
            if name:
                meta["assigned_name"] = name
            if truncated:
                meta["truncated"] = True
            items.append(
                ClassifiedItem(
                    value=value,
                    masked=mask(value, keep_front=4),
                    kind="unknown",
                    label="미상",
                    confidence="unknown",
                    format=_unknown_format(value),
                    source=source,
                    stage=1,
                    meta=meta,
                )
            )

    return items
