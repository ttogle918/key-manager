# SPDX-FileCopyrightText: 2026 [Your Name]
# SPDX-License-Identifier: MIT
"""dest_email·IP별 고정 윈도우 요율 제한 — 릴레이가 임의 주소 스팸 발송기로 악용되는 걸 막는다.

메모리 카운터만 쓴다(DB 없음) — manager-relay 전체의 "영구 저장소 없음" 설계와 일관됨.
"""
from __future__ import annotations

import threading
import time
from collections import defaultdict
from typing import Callable


class RateLimitExceeded(Exception):
    def __init__(self, retry_after: float) -> None:
        super().__init__(f"요청이 너무 많습니다 — {retry_after:.0f}초 후 다시 시도하세요")
        self.retry_after = retry_after


class RateLimiter:
    def __init__(
        self,
        limit: int,
        window_seconds: int = 3600,
        clock: Callable[[], float] = time.time,
    ) -> None:
        self._limit = limit
        self._window = window_seconds
        self._clock = clock
        self._lock = threading.Lock()
        self._hits: dict[str, list[float]] = defaultdict(list)

    def check(self, key: str) -> None:
        now = self._clock()
        with self._lock:
            hits = [t for t in self._hits[key] if now - t < self._window]
            if len(hits) >= self._limit:
                retry_after = self._window - (now - hits[0])
                self._hits[key] = hits
                raise RateLimitExceeded(retry_after)
            hits.append(now)
            self._hits[key] = hits
