<!--
SPDX-FileCopyrightText: 2026 [Your Name]
SPDX-License-Identifier: MIT
-->

# SYNC-2 이메일 릴레이 동기화 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 계정·클라우드 DB 없이, 목적지 이메일 입력 → 확인 링크 클릭 → 암호화 번들 첨부 메일이라는
2단계 SMTP 릴레이만으로 KeyLens 금고를 다른 기기로 옮길 수 있게 한다.

**Architecture:** 레포 안에 독립 배포형 서비스 `manager-relay/`(FastAPI, `backend/`와 같은 레벨)를
새로 만든다. 이 서비스는 메모리 dict(TTL)로 토큰만 임시 보관하고, DB·계정 없이 SMTP로만 이메일을
보낸다. 프론트엔드는 기존 SYNC-0 `/vault/export`로 만든 암호문 번들을 이 릴레이에 전달하는 새 모달을
추가한다. 복원은 기존 SYNC-0 "가져오기" 화면을 그대로 재사용 — 새 복호화 경로 없음.

**Tech Stack:** Python 3.13 + FastAPI(백엔드와 동일 버전 고정) + 표준 라이브러리 `smtplib`(새 런타임
의존성 0). 프론트는 기존 React + TypeScript + Zustand 스택 그대로.

**설계 스펙:** `docs/superpowers/specs/2026-08-26-sync2-email-relay-design.md` (이 계획은 그 문서의
승인된 설계를 그대로 구현한다 — 판단 근거는 그 문서를 참고)

## Global Constraints

- SPDX 헤더 2줄(`SPDX-FileCopyrightText: 2026 [Your Name]` / `SPDX-License-Identifier: MIT`)을
  새로 만드는 모든 파일 맨 위에 붙인다(주석 기호는 언어에 맞게).
- **httpx/`TestClient`를 쓰지 않는다** — `certifi`(MPL-2.0)를 끌어와 CLAUDE.md 라이선스 규칙에
  걸린다(`backend/requirements-dev.txt`에 이미 명시된 이 레포의 확립된 규칙). 백엔드류 테스트는
  전부 라우트 함수를 직접 호출한다(`backend/tests/test_vault_api.py` 패턴 그대로).
- 새 런타임 의존성을 추가하지 않는다(YAGNI) — 이메일 발송은 표준 라이브러리 `smtplib`/`email`만
  쓰고, 이메일 형식 검증도 정규식 하나로 충분히 해결한다(`pydantic[email]`의 `EmailStr`는
  `email-validator` 신규 의존성을 끌어오므로 쓰지 않는다).
- 의존성 버전은 고정(pinned)한다 — `manager-relay/requirements.txt`는 `backend/requirements.txt`와
  동일한 `fastapi`/`starlette`/`uvicorn` 버전을 그대로 맞춘다.
- 에러 메시지는 한국어·사용자 친화적으로("문제가 발생했어요 — 잠시 후 다시 시도해 보세요" 톤),
  이 레포의 기존 `frontend/src/api/client.ts` 관례를 그대로 따른다.
- 조용한 실패 금지 — 발송 실패는 반드시 명확한 HTTP 에러 코드로 드러낸다.
- 프론트엔드 새 UI는 `tsc --noEmit` + `npm run lint`(oxlint) + `npm run build`로 검증한다. 이
  레포는 React 컴포넌트/스토어용 자동 테스트 인프라가 없다(`docs/superpowers/specs/2026-08-09-keylens-env-package-design.md`에도 동일하게 기록된 관례) — 새로 만들지 않고 수동 브라우저
  확인으로 마무리한다.

---

### Task 1: `manager-relay/` 프로젝트 뼈대 + `token_store.py`

**Files:**
- Create: `manager-relay/requirements.txt`
- Create: `manager-relay/requirements-dev.txt`
- Create: `manager-relay/pytest.ini`
- Create: `manager-relay/.env.example`
- Create: `manager-relay/app/__init__.py`
- Create: `manager-relay/app/token_store.py`
- Create: `manager-relay/tests/__init__.py`
- Test: `manager-relay/tests/test_token_store.py`

**Interfaces:**
- Produces: `TokenStore(ttl_seconds: int = 900, clock: Callable[[], float] = time.time)` —
  `.issue(destination_email: str, bundle: dict) -> str`(토큰 발급),
  `.peek(token: str) -> PendingExport | None`(조회, 소진 안 함),
  `.consume(token: str) -> None`(1회용 소진). `PendingExport`는
  `destination_email: str`, `bundle: dict`, `expires_at: float` 필드를 갖는 dataclass.

- [ ] **Step 1: 디렉토리 뼈대 + 의존성 파일 작성**

`manager-relay/requirements.txt`:
```text
# SPDX-FileCopyrightText: 2026 [Your Name]
# SPDX-License-Identifier: MIT
#
# 런타임 의존성. backend/requirements.txt 와 동일 버전으로 고정 — 이미 라이선스 스캔을 통과한 조합.
fastapi==0.139.0      # MIT
starlette==1.3.1      # BSD-3-Clause
uvicorn==0.34.0       # BSD-3-Clause
pydantic==2.10.4      # MIT
```

`manager-relay/requirements-dev.txt`:
```text
# SPDX-FileCopyrightText: 2026 [Your Name]
# SPDX-License-Identifier: MIT
#
# 개발/테스트 의존성 (런타임 포함).
# httpx(TestClient)는 certifi(MPL-2.0)를 끌어와 CLAUDE.md 라이선스 규칙에 걸리므로
# 쓰지 않는다 — 테스트는 라우트 함수를 직접 호출한다(backend/tests 와 동일 관례).
-r requirements.txt
pytest==9.0.3         # MIT
```

`manager-relay/pytest.ini`:
```ini
[pytest]
pythonpath = .
testpaths = tests
```

`manager-relay/.env.example`:
```text
# SPDX-FileCopyrightText: 2026 [Your Name]
# SPDX-License-Identifier: MIT
#
# 이 파일은 템플릿입니다. 실제 값은 배포 환경(예: GCloud Cloud Run 환경변수)에만 넣고
# 절대 커밋하지 마세요. 이 서비스를 직접 배포하는 사람("매니저")만 이 값들을 채웁니다.

# SMTP 발송 자격증명 — Gmail이면 "앱 비밀번호"(2단계 인증 필요), Resend/SendGrid 등
# 어떤 SMTP 제공자로도 교체 가능(호스트/포트만 바꾸면 됨).
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=
SMTP_PASS=
SMTP_USE_TLS=true

# 확인 메일에 담을 이 서비스 자신의 공개 배포 주소(자격증명 아님 — 공개돼도 안전).
PUBLIC_BASE_URL=https://your-relay.example.com

# 어뷰징 방지 요율 제한(생략 시 기본값 사용).
RELAY_RATE_LIMIT_PER_EMAIL=3
RELAY_RATE_LIMIT_PER_IP=10
```

`manager-relay/app/__init__.py`:
```python
# SPDX-FileCopyrightText: 2026 [Your Name]
# SPDX-License-Identifier: MIT
"""KeyLens 매니저 릴레이 — 계정/DB 없이 SMTP로만 금고 번들을 전달하는 이메일 릴레이."""

__all__ = []
```

`manager-relay/tests/__init__.py`:
```python
# SPDX-FileCopyrightText: 2026 [Your Name]
# SPDX-License-Identifier: MIT
```

- [ ] **Step 2: REUSE 예외 목록에 새 설정 파일 등록**

`manager-relay/pytest.ini`·`.env.example`·`requirements-dev.txt`는 `backend/`의 동일 파일들과
똑같이 인라인 SPDX 헤더를 넣지 않는(또는 reuse 6.x CJK 오탐 회피용 안전장치가 필요한) 파일이다.
`.reuse/dep5`에 이미 있는 `backend/pytest.ini` / `backend/requirements-dev.txt` / `.env.example`
항목 옆에 이 세 파일을 추가하지 않으면 `reuse lint`(라이선스 체크리스트 필수 항목)가 실패한다.

`.reuse/dep5`의 마지막 `Files:` 블록(`관용적으로 SPDX 헤더를 넣지 않는 설정·생성·라이선스 파일`)을
다음으로 교체(기존 항목 유지 + 3줄 추가):
```text
Files:
  LICENSE
  .gitignore
  frontend/.gitignore
  .env.example
  backend/pytest.ini
  backend/requirements-dev.txt
  manager-relay/pytest.ini
  manager-relay/.env.example
  manager-relay/requirements-dev.txt
  keylens-env/pyproject.toml
  .claude/settings.json
  frontend/.oxlintrc.json
  frontend/tsconfig.json
  frontend/tsconfig.app.json
  frontend/tsconfig.node.json
  frontend/package.json
  frontend/package-lock.json
  frontend/index.html
  frontend/public/favicon.svg
Copyright: 2026 [Your Name]
License: MIT
```

- [ ] **Step 3: 실패하는 테스트 작성**

`manager-relay/tests/test_token_store.py`:
```python
# SPDX-FileCopyrightText: 2026 [Your Name]
# SPDX-License-Identifier: MIT
"""토큰 저장소 — 발급→조회→소진, TTL 만료를 검증한다. DB 없이 메모리 dict만 쓴다."""
from app.token_store import TokenStore


def test_issue_then_peek_returns_entry():
    store = TokenStore()
    token = store.issue("user@example.com", {"format": "klvault", "entries": []})
    entry = store.peek(token)
    assert entry is not None
    assert entry.destination_email == "user@example.com"
    assert entry.bundle == {"format": "klvault", "entries": []}


def test_peek_does_not_consume():
    store = TokenStore()
    token = store.issue("user@example.com", {})
    store.peek(token)
    assert store.peek(token) is not None  # 두 번째 조회에도 여전히 존재


def test_consume_removes_entry():
    store = TokenStore()
    token = store.issue("user@example.com", {})
    store.consume(token)
    assert store.peek(token) is None


def test_unknown_token_returns_none():
    store = TokenStore()
    assert store.peek("nonexistent-token") is None


def test_expired_token_returns_none():
    now = [1000.0]
    store = TokenStore(ttl_seconds=60, clock=lambda: now[0])
    token = store.issue("user@example.com", {})
    now[0] += 61  # TTL 경과
    assert store.peek(token) is None


def test_not_yet_expired_token_still_valid():
    now = [1000.0]
    store = TokenStore(ttl_seconds=60, clock=lambda: now[0])
    token = store.issue("user@example.com", {})
    now[0] += 59  # TTL 직전
    assert store.peek(token) is not None
```

- [ ] **Step 4: 테스트 실행 → 실패 확인**

Run (작업 디렉토리 `manager-relay/`): `python -m pytest tests/test_token_store.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.token_store'`

- [ ] **Step 5: `token_store.py` 구현**

`manager-relay/app/token_store.py`:
```python
# SPDX-FileCopyrightText: 2026 [Your Name]
# SPDX-License-Identifier: MIT
"""확인 대기 중인 이메일 내보내기 요청을 메모리에만 잠깐 보관한다.

DB가 아니다 — 발송 성공(consume) 또는 TTL 만료(자동 스윕)로 반드시 사라진다.
매니저 서버가 재시작되면(예: 서버리스 스케일-투-제로) 대기 중이던 요청은 유실될 수
있으나, 사용자가 다시 요청하면 되므로 이 트레이드오프를 그대로 받아들인다
(docs/superpowers/specs/2026-08-26-sync2-email-relay-design.md 판단 3).
"""
from __future__ import annotations

import secrets
import threading
import time
from dataclasses import dataclass
from typing import Callable

DEFAULT_TTL_SECONDS = 15 * 60


@dataclass
class PendingExport:
    destination_email: str
    bundle: dict
    expires_at: float


class TokenStore:
    def __init__(
        self,
        ttl_seconds: int = DEFAULT_TTL_SECONDS,
        clock: Callable[[], float] = time.time,
    ) -> None:
        self._ttl = ttl_seconds
        self._clock = clock
        self._lock = threading.Lock()
        self._pending: dict[str, PendingExport] = {}

    def issue(self, destination_email: str, bundle: dict) -> str:
        token = secrets.token_urlsafe(32)
        with self._lock:
            self._sweep_locked()
            self._pending[token] = PendingExport(
                destination_email=destination_email,
                bundle=bundle,
                expires_at=self._clock() + self._ttl,
            )
        return token

    def peek(self, token: str) -> PendingExport | None:
        """유효하면(존재+미만료) 반환한다 — 소진하지 않는다(발송 실패 시 재시도용)."""
        with self._lock:
            self._sweep_locked()
            return self._pending.get(token)

    def consume(self, token: str) -> None:
        """발송 성공 후 1회용으로 소진한다. 없는 토큰이어도 조용히 무시한다."""
        with self._lock:
            self._pending.pop(token, None)

    def _sweep_locked(self) -> None:
        now = self._clock()
        expired = [t for t, e in self._pending.items() if e.expires_at <= now]
        for t in expired:
            del self._pending[t]
```

- [ ] **Step 6: 테스트 실행 → 통과 확인**

Run: `python -m pytest tests/test_token_store.py -v`
Expected: PASS(6개 전부)

- [ ] **Step 7: `reuse lint`로 헤더·예외 등록 확인(선택, 로컬에 `reuse` 설치돼 있으면)**

Run: `pip install "reuse==6.2.0" && reuse lint`
Expected: 새로 만든 `manager-relay/` 파일들이 전부 통과(헤더 있음 또는 dep5 예외 등록됨). 로컬에
`reuse`를 설치하지 않았다면 이 스텝은 건너뛰어도 되고, 어차피 CI의 `license` 잡이 push 시 검증한다.

- [ ] **Step 8: 커밋**

```bash
git add manager-relay/ .reuse/dep5
git commit -m "$(cat <<'EOF'
feat(manager-relay): 프로젝트 뼈대 + 메모리 토큰 저장소(TTL)

DB 없이 확인 대기 요청을 메모리+TTL로만 보관하는 TokenStore. 발급/조회/
소진/만료 스윕을 단위테스트로 검증.

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
EOF
)"
```

---

### Task 2: `rate_limit.py` — 어뷰징 방지 요율 제한

**Files:**
- Create: `manager-relay/app/rate_limit.py`
- Test: `manager-relay/tests/test_rate_limit.py`

**Interfaces:**
- Consumes: 없음(독립 모듈)
- Produces: `RateLimitExceeded(retry_after: float)` 예외(`.retry_after` 속성).
  `RateLimiter(limit: int, window_seconds: int = 3600, clock: Callable[[], float] = time.time)` —
  `.check(key: str) -> None`(한도 초과 시 `RateLimitExceeded` 발생, 아니면 카운트 증가 후 반환).

- [ ] **Step 1: 실패하는 테스트 작성**

`manager-relay/tests/test_rate_limit.py`:
```python
# SPDX-FileCopyrightText: 2026 [Your Name]
# SPDX-License-Identifier: MIT
"""고정 윈도우 요율 제한 — dest_email/IP별로 시간당 요청 횟수를 독립 집계한다."""
import pytest

from app.rate_limit import RateLimitExceeded, RateLimiter


def test_allows_up_to_limit():
    limiter = RateLimiter(limit=3, window_seconds=3600)
    for _ in range(3):
        limiter.check("user@example.com")  # 예외 없이 통과해야 함


def test_raises_after_limit_exceeded():
    limiter = RateLimiter(limit=3, window_seconds=3600)
    for _ in range(3):
        limiter.check("user@example.com")
    with pytest.raises(RateLimitExceeded):
        limiter.check("user@example.com")


def test_different_keys_independent():
    limiter = RateLimiter(limit=1, window_seconds=3600)
    limiter.check("a@example.com")
    limiter.check("b@example.com")  # 다른 키라 별도 한도 — 예외 없어야 함


def test_window_resets_after_elapsed_time():
    now = [1000.0]
    limiter = RateLimiter(limit=1, window_seconds=60, clock=lambda: now[0])
    limiter.check("user@example.com")
    now[0] += 61  # 윈도우 경과
    limiter.check("user@example.com")  # 다시 허용돼야 함


def test_retry_after_reported_on_exceeded():
    now = [1000.0]
    limiter = RateLimiter(limit=1, window_seconds=60, clock=lambda: now[0])
    limiter.check("user@example.com")
    now[0] += 10
    with pytest.raises(RateLimitExceeded) as exc_info:
        limiter.check("user@example.com")
    assert 45 <= exc_info.value.retry_after <= 50
```

- [ ] **Step 2: 테스트 실행 → 실패 확인**

Run: `python -m pytest tests/test_rate_limit.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.rate_limit'`

- [ ] **Step 3: `rate_limit.py` 구현**

`manager-relay/app/rate_limit.py`:
```python
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
```

- [ ] **Step 4: 테스트 실행 → 통과 확인**

Run: `python -m pytest tests/test_rate_limit.py -v`
Expected: PASS(5개 전부)

- [ ] **Step 5: 커밋**

```bash
git add manager-relay/app/rate_limit.py manager-relay/tests/test_rate_limit.py
git commit -m "$(cat <<'EOF'
feat(manager-relay): dest_email/IP별 요율 제한(RateLimiter)

임의 이메일 주소로 릴레이를 스팸 발송기로 악용하는 걸 막기 위한 고정
윈도우 카운터. DB 없이 메모리로만 집계.

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
EOF
)"
```

---

### Task 3: `mailer.py` — SMTP 발송

**Files:**
- Create: `manager-relay/app/mailer.py`
- Test: `manager-relay/tests/test_mailer.py`

**Interfaces:**
- Consumes: 없음(독립 모듈)
- Produces: `MailSendError(Exception)`. `SmtpConfig(host, port, user, password, use_tls=True)` +
  `SmtpConfig.from_env(env: dict[str, str] | None = None) -> SmtpConfig`(env에 `SMTP_HOST`/
  `SMTP_USER`/`SMTP_PASS` 없으면 `RuntimeError`). `send_confirm_email(config: SmtpConfig,
  destination_email: str, confirm_url: str) -> None`. `send_bundle_email(config: SmtpConfig,
  destination_email: str, bundle_json: str) -> None`. 둘 다 SMTP 오류 시 `MailSendError`.

- [ ] **Step 1: 실패하는 테스트 작성**

`manager-relay/tests/test_mailer.py`:
```python
# SPDX-FileCopyrightText: 2026 [Your Name]
# SPDX-License-Identifier: MIT
"""SMTP 발송 — smtplib.SMTP를 monkeypatch해 실제 네트워크 없이 호출 인자만 검증한다."""
import smtplib

import pytest

from app.mailer import MailSendError, SmtpConfig, send_bundle_email, send_confirm_email

CONFIG = SmtpConfig(host="smtp.example.com", port=587, user="relay@example.com", password="pw")


class FakeSmtp:
    sent_messages = []

    def __init__(self, host, port, timeout=10):
        self.host = host
        self.port = port

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def starttls(self):
        pass

    def login(self, user, password):
        self.user = user
        self.password = password

    def send_message(self, msg):
        FakeSmtp.sent_messages.append(msg)


@pytest.fixture(autouse=True)
def _reset_fake_smtp(monkeypatch):
    FakeSmtp.sent_messages = []
    monkeypatch.setattr(smtplib, "SMTP", FakeSmtp)


def test_smtp_config_from_env_reads_required_fields():
    config = SmtpConfig.from_env(
        {"SMTP_HOST": "h", "SMTP_PORT": "2525", "SMTP_USER": "u", "SMTP_PASS": "p"}
    )
    assert config.host == "h" and config.port == 2525 and config.user == "u"


def test_smtp_config_from_env_missing_required_raises():
    with pytest.raises(RuntimeError):
        SmtpConfig.from_env({})


def test_send_confirm_email_delivers_link():
    send_confirm_email(CONFIG, "dest@example.com", "https://relay.example.com/sync/confirm?token=abc")
    assert len(FakeSmtp.sent_messages) == 1
    msg = FakeSmtp.sent_messages[0]
    assert msg["To"] == "dest@example.com"
    assert "https://relay.example.com/sync/confirm?token=abc" in msg.get_content()


def test_send_bundle_email_attaches_json():
    send_bundle_email(CONFIG, "dest@example.com", '{"format": "klvault"}')
    assert len(FakeSmtp.sent_messages) == 1
    msg = FakeSmtp.sent_messages[0]
    assert msg["To"] == "dest@example.com"
    attachments = list(msg.iter_attachments())
    assert len(attachments) == 1
    assert attachments[0].get_content().decode("utf-8") == '{"format": "klvault"}'


def test_send_error_normalizes_to_mail_send_error(monkeypatch):
    class BrokenSmtp(FakeSmtp):
        def login(self, user, password):
            raise smtplib.SMTPAuthenticationError(535, b"bad credentials")

    monkeypatch.setattr(smtplib, "SMTP", BrokenSmtp)
    with pytest.raises(MailSendError):
        send_confirm_email(CONFIG, "dest@example.com", "https://relay.example.com/sync/confirm?token=abc")
```

- [ ] **Step 2: 테스트 실행 → 실패 확인**

Run: `python -m pytest tests/test_mailer.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.mailer'`

- [ ] **Step 3: `mailer.py` 구현**

`manager-relay/app/mailer.py`:
```python
# SPDX-FileCopyrightText: 2026 [Your Name]
# SPDX-License-Identifier: MIT
"""SMTP 발송 — 표준 라이브러리 smtplib만 쓴다(새 런타임 의존성 0).

Gmail 앱 비밀번호부터 Resend/SendGrid의 SMTP 엔드포인트까지 env 값만 바꾸면 그대로
교체된다(docs/superpowers/specs/2026-08-26-sync2-email-relay-design.md 판단 1).
"""
from __future__ import annotations

import os
import smtplib
from email.message import EmailMessage


class MailSendError(Exception):
    """SMTP 발송 실패(네트워크·인증 오류)를 이 예외 하나로 정규화한다."""


class SmtpConfig:
    def __init__(self, host: str, port: int, user: str, password: str, use_tls: bool = True) -> None:
        self.host = host
        self.port = port
        self.user = user
        self.password = password
        self.use_tls = use_tls

    @classmethod
    def from_env(cls, env: dict[str, str] | None = None) -> "SmtpConfig":
        e = env if env is not None else os.environ
        missing = [k for k in ("SMTP_HOST", "SMTP_USER", "SMTP_PASS") if not e.get(k)]
        if missing:
            raise RuntimeError(f"SMTP 설정이 없습니다 — 환경변수 {', '.join(missing)} 를 설정하세요")
        return cls(
            host=e["SMTP_HOST"],
            port=int(e.get("SMTP_PORT", "587")),
            user=e["SMTP_USER"],
            password=e["SMTP_PASS"],
            use_tls=e.get("SMTP_USE_TLS", "true").lower() != "false",
        )


def send_confirm_email(config: SmtpConfig, destination_email: str, confirm_url: str) -> None:
    msg = EmailMessage()
    msg["Subject"] = "[KeyLens] 금고 내보내기 요청 확인"
    msg["From"] = config.user
    msg["To"] = destination_email
    msg.set_content(
        "KeyLens에서 이 주소로 금고 내보내기 요청이 있었습니다.\n\n"
        f"본인이 요청한 것이 맞다면 아래 링크를 클릭해 실제 파일을 받으세요:\n{confirm_url}\n\n"
        "요청한 적이 없다면 이 메일을 무시하세요 — 클릭하지 않으면 아무 일도 일어나지 않습니다.\n"
        "이 링크는 15분간만 유효합니다."
    )
    _send(config, msg)


def send_bundle_email(config: SmtpConfig, destination_email: str, bundle_json: str) -> None:
    msg = EmailMessage()
    msg["Subject"] = "[KeyLens] 암호화된 금고 백업 파일"
    msg["From"] = config.user
    msg["To"] = destination_email
    msg.set_content(
        "요청하신 KeyLens 금고 백업 파일을 첨부했습니다.\n\n"
        "이 파일은 전부 암호문입니다 — 원래 금고의 마스터 비밀번호가 있어야만 열 수 있습니다.\n"
        "다른 기기의 KeyLens에서 '가져오기'로 이 첨부파일을 지정해 복원하세요."
    )
    msg.add_attachment(
        bundle_json.encode("utf-8"),
        maintype="application",
        subtype="json",
        filename="keylens-vault.klvault.json",
    )
    _send(config, msg)


def _send(config: SmtpConfig, msg: EmailMessage) -> None:
    try:
        with smtplib.SMTP(config.host, config.port, timeout=10) as smtp:
            if config.use_tls:
                smtp.starttls()
            smtp.login(config.user, config.password)
            smtp.send_message(msg)
    except (smtplib.SMTPException, OSError) as e:
        raise MailSendError(f"메일 발송 실패: {e}") from e
```

- [ ] **Step 4: 테스트 실행 → 통과 확인**

Run: `python -m pytest tests/test_mailer.py -v`
Expected: PASS(5개 전부)

- [ ] **Step 5: 커밋**

```bash
git add manager-relay/app/mailer.py manager-relay/tests/test_mailer.py
git commit -m "$(cat <<'EOF'
feat(manager-relay): SMTP 발송(mailer) — 확인 메일/첨부 메일 2종

표준 라이브러리 smtplib만 사용(새 의존성 0). Gmail 앱 비밀번호부터
Resend/SendGrid SMTP까지 env만 바꾸면 그대로 교체 가능.

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
EOF
)"
```

---

### Task 4: `models.py` + `main.py` — `/sync/request`, `/sync/confirm` 엔드포인트

**Files:**
- Create: `manager-relay/app/models.py`
- Create: `manager-relay/app/main.py`
- Create: `manager-relay/README.md`
- Test: `manager-relay/tests/test_main.py`

**Interfaces:**
- Consumes: `TokenStore`(Task 1), `RateLimiter`/`RateLimitExceeded`(Task 2),
  `SmtpConfig`/`MailSendError`/`send_confirm_email`/`send_bundle_email`(Task 3).
- Produces: `SyncRequestBody(destination_email: str, bundle: dict)`(pydantic). 모듈 전역
  `app`(FastAPI), `SMTP`(SmtpConfig), `STORE`(TokenStore), `RATE_PER_EMAIL`/`RATE_PER_IP`
  (RateLimiter), `PUBLIC_BASE_URL`(str). 라우트 함수 `sync_request(body: SyncRequestBody,
  client_ip: str = Depends(_client_ip)) -> dict`, `sync_confirm(token: str) -> str`(HTML).

- [ ] **Step 1: 실패하는 테스트 작성**

`manager-relay/tests/test_main.py`:
```python
# SPDX-FileCopyrightText: 2026 [Your Name]
# SPDX-License-Identifier: MIT
"""엔드포인트 상태코드/부수효과 테스트. httpx(certifi/MPL) 회피 — 라우트 함수 직접 호출."""
import pytest
from fastapi import HTTPException

from app import main
from app.mailer import MailSendError
from app.models import SyncRequestBody
from app.rate_limit import RateLimiter
from app.token_store import TokenStore

BUNDLE = {"format": "klvault", "version": 1, "entries": []}


@pytest.fixture
def relay(monkeypatch):
    """main 의 전역 상태를 매 테스트마다 새로 교체 — 테스트 간 간섭 방지."""
    monkeypatch.setattr(main, "STORE", TokenStore())
    monkeypatch.setattr(main, "RATE_PER_EMAIL", RateLimiter(limit=3, window_seconds=3600))
    monkeypatch.setattr(main, "RATE_PER_IP", RateLimiter(limit=10, window_seconds=3600))
    sent = {"confirm": [], "bundle": []}

    def fake_confirm(config, destination_email, confirm_url):
        sent["confirm"].append((destination_email, confirm_url))

    def fake_bundle(config, destination_email, bundle_json):
        sent["bundle"].append((destination_email, bundle_json))

    monkeypatch.setattr(main, "send_confirm_email", fake_confirm)
    monkeypatch.setattr(main, "send_bundle_email", fake_bundle)
    return sent


def test_sync_request_issues_token_and_sends_confirm_email(relay):
    result = main.sync_request(
        SyncRequestBody(destination_email="dest@example.com", bundle=BUNDLE), client_ip="1.2.3.4"
    )
    assert result == {"requested": True}
    assert len(relay["confirm"]) == 1
    dest, confirm_url = relay["confirm"][0]
    assert dest == "dest@example.com"
    assert "/sync/confirm?token=" in confirm_url


def test_sync_request_rate_limited_by_email(relay):
    for _ in range(3):
        main.sync_request(
            SyncRequestBody(destination_email="dest@example.com", bundle=BUNDLE), client_ip="1.2.3.4"
        )
    with pytest.raises(HTTPException) as exc_info:
        main.sync_request(
            SyncRequestBody(destination_email="dest@example.com", bundle=BUNDLE), client_ip="9.9.9.9"
        )
    assert exc_info.value.status_code == 429


def test_sync_request_confirm_email_failure_raises_502(relay, monkeypatch):
    def failing_send(config, destination_email, confirm_url):
        raise MailSendError("boom")

    monkeypatch.setattr(main, "send_confirm_email", failing_send)
    with pytest.raises(HTTPException) as exc_info:
        main.sync_request(
            SyncRequestBody(destination_email="dest@example.com", bundle=BUNDLE), client_ip="1.2.3.4"
        )
    assert exc_info.value.status_code == 502


def test_sync_confirm_valid_token_sends_bundle_and_consumes(relay):
    main.sync_request(
        SyncRequestBody(destination_email="dest@example.com", bundle=BUNDLE), client_ip="1.2.3.4"
    )
    _, confirm_url = relay["confirm"][0]
    token = confirm_url.split("token=")[1]

    html = main.sync_confirm(token)
    assert "발송" in html
    assert len(relay["bundle"]) == 1
    dest, bundle_json = relay["bundle"][0]
    assert dest == "dest@example.com"
    assert '"format": "klvault"' in bundle_json or '"format":"klvault"' in bundle_json

    # 1회용 소진 — 같은 토큰 재사용은 410
    with pytest.raises(HTTPException) as exc_info:
        main.sync_confirm(token)
    assert exc_info.value.status_code == 410


def test_sync_confirm_unknown_token_returns_410(relay):
    with pytest.raises(HTTPException) as exc_info:
        main.sync_confirm("nonexistent-token")
    assert exc_info.value.status_code == 410


def test_sync_confirm_bundle_send_failure_keeps_token_for_retry(relay, monkeypatch):
    main.sync_request(
        SyncRequestBody(destination_email="dest@example.com", bundle=BUNDLE), client_ip="1.2.3.4"
    )
    _, confirm_url = relay["confirm"][0]
    token = confirm_url.split("token=")[1]

    def failing_send(config, destination_email, bundle_json):
        raise MailSendError("boom")

    monkeypatch.setattr(main, "send_bundle_email", failing_send)
    with pytest.raises(HTTPException) as exc_info:
        main.sync_confirm(token)
    assert exc_info.value.status_code == 502

    # 소진되지 않았으므로 재시도(다음 클릭)는 여전히 유효한 토큰으로 처리돼야 함
    monkeypatch.setattr(main, "send_bundle_email", lambda c, d, b: relay["bundle"].append((d, b)))
    main.sync_confirm(token)
    assert len(relay["bundle"]) == 1
```

- [ ] **Step 2: 테스트 실행 → 실패 확인**

Run: `python -m pytest tests/test_main.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.main'`(먼저 `SMTP_HOST` 등 env 미설정으로
`RuntimeError`가 날 수도 있음 — 이는 Step 4에서 `tests/conftest.py`로 해결한다)

- [ ] **Step 3: 테스트용 기본 env 설정 — `conftest.py`**

`main.py`는 기동 시 `SmtpConfig.from_env()`를 즉시 호출해 실패하면 바로 죽는 fail-fast 설계다(운영
환경에서 SMTP 설정을 빠뜨리고 배포하는 실수를 막기 위함). 테스트 프로세스에도 더미 값을 미리
심어둔다.

`manager-relay/tests/conftest.py`:
```python
# SPDX-FileCopyrightText: 2026 [Your Name]
# SPDX-License-Identifier: MIT
"""app.main import 시점의 fail-fast(SMTP env 필수) 를 테스트에서도 만족시키는 더미 값."""
import os

os.environ.setdefault("SMTP_HOST", "smtp.test.invalid")
os.environ.setdefault("SMTP_PORT", "587")
os.environ.setdefault("SMTP_USER", "relay@test.invalid")
os.environ.setdefault("SMTP_PASS", "test-password")
os.environ.setdefault("PUBLIC_BASE_URL", "http://localhost:8080")
```

- [ ] **Step 4: `models.py` + `main.py` 구현**

`manager-relay/app/models.py`:
```python
# SPDX-FileCopyrightText: 2026 [Your Name]
# SPDX-License-Identifier: MIT
"""엔드포인트 입출력 스키마."""
from __future__ import annotations

import re

from pydantic import BaseModel, field_validator

# pydantic[email]의 EmailStr는 email-validator 신규 의존성을 끌어오므로 정규식으로 직접 검증한다.
_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


class SyncRequestBody(BaseModel):
    destination_email: str
    bundle: dict

    @field_validator("destination_email")
    @classmethod
    def _validate_email(cls, v: str) -> str:
        if not _EMAIL_RE.match(v):
            raise ValueError("올바른 이메일 형식이 아니에요")
        return v
```

`manager-relay/app/main.py`:
```python
# SPDX-FileCopyrightText: 2026 [Your Name]
# SPDX-License-Identifier: MIT
"""KeyLens 매니저 릴레이 API.

계정·DB 없이 SMTP로만 암호화 금고 번들을 목적지 이메일로 전달한다. 이 서버는
평문을 절대 보지 않고(번들은 이미 암호문), 요청 처리가 끝나면 아무것도 영구 저장하지
않는다(docs/superpowers/specs/2026-08-26-sync2-email-relay-design.md).
"""
from __future__ import annotations

import json
import os

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse

from .mailer import MailSendError, SmtpConfig, send_bundle_email, send_confirm_email
from .models import SyncRequestBody
from .rate_limit import RateLimitExceeded, RateLimiter
from .token_store import TokenStore

app = FastAPI(title="KeyLens Manager Relay", version="0.1.0")

# 이 릴레이는 자격증명을 쓰지 않는 공개 API라, 배포되는 exe가 어떤 로컬 오리진에서
# 오든(사용자마다 포트가 다를 수 있음) 그대로 허용한다. 쿠키/세션이 없어 안전하다.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["POST", "GET"],
    allow_headers=["*"],
)

# 기동 시 SMTP 설정이 없으면 바로 실패한다(fail-fast) — 자격증명 없이 조용히 떠서
# "되는 척"하지 않는다.
SMTP = SmtpConfig.from_env()
STORE = TokenStore()

_int = lambda k, d: int(os.environ.get(k, d))  # noqa: E731
RATE_PER_EMAIL = RateLimiter(limit=_int("RELAY_RATE_LIMIT_PER_EMAIL", 3))
RATE_PER_IP = RateLimiter(limit=_int("RELAY_RATE_LIMIT_PER_IP", 10))
PUBLIC_BASE_URL = os.environ.get("PUBLIC_BASE_URL", "http://localhost:8080").rstrip("/")


def _client_ip(request: Request) -> str:
    return request.client.host if request.client else "unknown"


@app.post("/sync/request", status_code=202)
def sync_request(body: SyncRequestBody, client_ip: str = Depends(_client_ip)) -> dict:
    try:
        RATE_PER_EMAIL.check(body.destination_email)
        RATE_PER_IP.check(client_ip)
    except RateLimitExceeded as e:
        raise HTTPException(
            status_code=429, detail=str(e), headers={"Retry-After": str(int(e.retry_after))}
        ) from e

    token = STORE.issue(body.destination_email, body.bundle)
    confirm_url = f"{PUBLIC_BASE_URL}/sync/confirm?token={token}"
    try:
        send_confirm_email(SMTP, body.destination_email, confirm_url)
    except MailSendError as e:
        STORE.consume(token)
        raise HTTPException(
            status_code=502, detail="확인 메일 발송에 실패했어요 — 잠시 후 다시 시도하세요"
        ) from e
    return {"requested": True}


@app.get("/sync/confirm", response_class=HTMLResponse)
def sync_confirm(token: str) -> str:
    entry = STORE.peek(token)
    if entry is None:
        raise HTTPException(
            status_code=410,
            detail="요청이 만료되었거나 이미 처리됐어요 — KeyLens에서 다시 내보내기를 시도하세요",
        )
    try:
        send_bundle_email(SMTP, entry.destination_email, json.dumps(entry.bundle))
    except MailSendError as e:
        raise HTTPException(
            status_code=502, detail="파일 발송에 실패했어요 — 이 링크를 다시 눌러 재시도하세요"
        ) from e
    STORE.consume(token)
    return (
        "<html><body><h1>발송 완료</h1>"
        "<p>요청하신 파일을 이메일로 보냈습니다. 이메일함을 확인하세요.</p></body></html>"
    )


DEFAULT_PORT = 8090

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=DEFAULT_PORT)
```

- [ ] **Step 5: 테스트 실행 → 통과 확인**

Run: `python -m pytest tests/test_main.py -v`
Expected: PASS(6개 전부)

- [ ] **Step 6: 전체 스위트 재확인**

Run: `python -m pytest -v`
Expected: PASS(Task 1~4의 모든 테스트, 총 22개)

- [ ] **Step 7: 셀프호스트 안내 README 작성**

`manager-relay/README.md`:
```markdown
<!--
SPDX-FileCopyrightText: 2026 [Your Name]
SPDX-License-Identifier: MIT
-->
# KeyLens 매니저 릴레이

계정·DB 없이 **SMTP로만** KeyLens 금고 번들을 이메일로 전달하는 독립 배포형 서비스입니다.
이 코드는 레포에 있지만 **실행 서버가 아닙니다** — 이 기능을 쓰고 싶은 사람("매니저")이
자기 SMTP 자격증명으로 직접 배포해야 동작합니다. 설계 배경은
[`docs/superpowers/specs/2026-08-26-sync2-email-relay-design.md`](../docs/superpowers/specs/2026-08-26-sync2-email-relay-design.md)를 참고하세요.

## 로컬 실행

```bash
cd manager-relay
python -m venv .venv && . .venv/Scripts/activate  # Windows(Git Bash). macOS/Linux는 source .venv/bin/activate
pip install -r requirements-dev.txt
cp .env.example .env  # 값 채우기 — Gmail이면 앱 비밀번호 필요(2단계 인증 계정)
set -a && source .env && set +a
python -m app.main  # http://localhost:8090
```

## 배포(예: GCloud Cloud Run)

`SMTP_HOST`/`SMTP_PORT`/`SMTP_USER`/`SMTP_PASS`/`PUBLIC_BASE_URL`을 배포 환경변수로 설정하세요.
**`min-instances=1`을 권장**합니다 — 이 서비스는 확인 대기 중인 요청을 프로세스 메모리에만
들고 있어서(TTL 15분), 스케일-투-제로로 인스턴스가 재활용되면 그 사이의 요청이 유실될 수
있습니다(사용자가 다시 요청하면 됩니다 — 설계 문서의 판단 3 참고).

## 프론트엔드 연결

배포한 주소를 KeyLens 프론트의 `VITE_SYNC_RELAY_URL`에 설정하면 "이메일로 내보내기" 버튼이
나타납니다(미설정 시 자동으로 숨겨짐 — `frontend/.env.example` 참고).
```

- [ ] **Step 8: 커밋**

```bash
git add manager-relay/
git commit -m "$(cat <<'EOF'
feat(manager-relay): /sync/request, /sync/confirm 엔드포인트 + README

2단계 발송(확인 링크 → 첨부) 흐름을 엔드투엔드로 연결. CORS는 배포되는
exe가 임의 로컬 오리진에서 호출할 수 있도록 와일드카드 허용(공개
API·쿠키 없음이라 안전). 셀프호스트 안내 README 추가.

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
EOF
)"
```

---

### Task 5: 프론트엔드 — "이메일로 내보내기" UI

**Files:**
- Create: `frontend/src/lib/syncRelay.ts`
- Modify: `frontend/src/store/keylensStore.ts:134`(state 필드), `:253`(액션 타입 선언),
  `:328`(초기 state), `:1107-1108` 부근(액션 구현 추가)
- Modify: `frontend/src/components/modals/Modals.tsx`(새 `EmailSyncModal` 컴포넌트 추가)
- Modify: `frontend/src/App.tsx:19,90-94`(import + 렌더)
- Modify: `frontend/src/components/screens/VaultScreen.tsx`(버튼 추가)
- Modify: `.env.example`(루트) — `VITE_SYNC_RELAY_URL` 안내 추가

**Interfaces:**
- Consumes: `manager-relay`의 `POST /sync/request`(Task 4). `vaultApi.exportBundle()`(기존
  SYNC-0, `frontend/src/api/client.ts:188`).
- Produces: `syncRelayConfigured: boolean`, `requestEmailExport(destinationEmail: string, bundle:
  unknown, timeoutMs?: number) => Promise<void>`, `SyncRelayError`(모두 `lib/syncRelay.ts`).
  스토어에 `emailSyncOpen: boolean`, `openEmailSync(): void`, `closeEmailSync(): void`,
  `emailExport(destEmail: string): Promise<boolean>` 추가.

- [ ] **Step 1: `lib/syncRelay.ts` 작성**

`frontend/src/lib/syncRelay.ts`:
```typescript
// SPDX-FileCopyrightText: 2026 [Your Name]
// SPDX-License-Identifier: MIT
/**
 * SYNC-2(재설계) — 이메일 릴레이 동기화 클라이언트.
 *
 * 릴레이 서버 주소는 비밀이 아니다(공개 URL일 뿐) — 실제 자격증명(SMTP)은 그 릴레이
 * 서버 자신의 배포 환경변수에만 있고, 이 프론트/exe에는 절대 들어오지 않는다.
 * 설계 근거: docs/superpowers/specs/2026-08-26-sync2-email-relay-design.md
 */
const RELAY_URL = (import.meta.env.VITE_SYNC_RELAY_URL as string | undefined)?.replace(/\/$/, '')

/** false면 이메일 동기화 UI 자체를 숨긴다 — 설정 안 된 채로 "되는 척"하지 않는다. */
export const syncRelayConfigured = Boolean(RELAY_URL)

export class SyncRelayError extends Error {}

/** POST /sync/request — 확인 메일 발송을 요청한다(실제 첨부는 사용자가 그 메일의 링크를 눌러야 감). */
export async function requestEmailExport(
  destinationEmail: string,
  bundle: unknown,
  timeoutMs = 10000,
): Promise<void> {
  if (!RELAY_URL) throw new SyncRelayError('이메일 동기화가 설정되지 않았어요')
  const ctrl = new AbortController()
  const timer = setTimeout(() => ctrl.abort(), timeoutMs)
  try {
    const res = await fetch(`${RELAY_URL}/sync/request`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ destination_email: destinationEmail, bundle }),
      signal: ctrl.signal,
    })
    if (!res.ok) {
      if (res.status === 429) {
        throw new SyncRelayError('요청이 너무 많아요 — 잠시 후 다시 시도하세요')
      }
      throw new SyncRelayError(`문제가 발생했어요 (오류 ${res.status}) — 잠시 후 다시 시도해 보세요.`)
    }
  } catch (e) {
    if (e instanceof SyncRelayError) throw e
    if (e instanceof DOMException && e.name === 'AbortError') {
      throw new SyncRelayError('응답이 너무 늦어요 — 다시 시도해 보세요.')
    }
    throw new SyncRelayError('이메일 동기화 서버에 연결할 수 없어요 — 잠시 후 다시 시도하세요.')
  } finally {
    clearTimeout(timer)
  }
}
```

- [ ] **Step 2: 스토어에 state 필드 추가**

`frontend/src/store/keylensStore.ts:134` 근처(`syncOpen: boolean` 바로 뒤)에 추가:
```typescript
  /** 이메일로 내보내기(SYNC-2 재설계) 모달 열림 여부. */
  emailSyncOpen: boolean
```

- [ ] **Step 3: 스토어 액션 타입 선언 추가**

`frontend/src/store/keylensStore.ts:253` 근처(`importVault` 선언 바로 뒤)에 추가:
```typescript
  /** 이메일 릴레이로 내보내기(SYNC-2 재설계, 계정/DB 없음). */
  openEmailSync: () => void
  closeEmailSync: () => void
  emailExport: (destEmail: string) => Promise<boolean>
```

- [ ] **Step 4: 초기 state 추가**

`frontend/src/store/keylensStore.ts:328` 근처(`syncOpen: false,` 바로 뒤)에 추가:
```typescript
    emailSyncOpen: false,
```

- [ ] **Step 5: import 추가**

`frontend/src/store/keylensStore.ts` 상단 import 블록(다른 `@/lib/*` import 옆, 예:
`import { envText, jwtExp, passwordPolicyError, today } from '@/lib/format'` 다음 줄)에 추가:
```typescript
import { requestEmailExport, SyncRelayError } from '@/lib/syncRelay'
```

- [ ] **Step 6: 액션 구현 추가**

`frontend/src/store/keylensStore.ts`의 `closeSync: () => set({ syncOpen: false }),` 바로 뒤(기존
`importVault` 정의 앞)에 추가:
```typescript
    openEmailSync: () => set({ emailSyncOpen: true }),
    closeEmailSync: () => set({ emailSyncOpen: false }),
    emailExport: async (destEmail) => {
      if (get().locked) {
        get().showToast('잠금 상태에서는 내보낼 수 없어요 — 먼저 잠금을 해제하세요')
        return false
      }
      try {
        const bundle = await vaultApi.exportBundle()
        await requestEmailExport(destEmail, bundle)
        set({ emailSyncOpen: false })
        get().showToast('확인 메일을 보냈어요 — 메일함에서 링크를 클릭하면 실제 파일이 발송됩니다')
        return true
      } catch (e) {
        if (e instanceof VaultApiError && e.status === 401) {
          set({ locked: true })
          get().showToast('금고가 잠겨 내보낼 수 없어요 — 잠금을 해제하세요')
        } else if (e instanceof SyncRelayError) {
          get().showToast(e.message)
        } else {
          get().showToast('내보내기 실패 — 잠시 후 다시 시도해 보세요')
        }
        return false
      }
    },
```

- [ ] **Step 7: `EmailSyncModal` 컴포넌트 추가**

`frontend/src/components/modals/Modals.tsx` 맨 끝(`EnvModal` 정의 뒤)에 추가:
```typescript
/** 이메일로 내보내기 다이얼로그(SYNC-2 재설계) — 목적지 이메일 입력 → 확인 메일 발송 요청. */
export function EmailSyncModal() {
  const open = useKeylens((s) => s.emailSyncOpen)
  const close = useKeylens((s) => s.closeEmailSync)
  const emailExport = useKeylens((s) => s.emailExport)
  const [email, setEmail] = useState('')
  const [busy, setBusy] = useState(false)

  useEffect(() => {
    if (open) {
      setEmail('')
      setBusy(false)
    }
  }, [open])

  const canRun = /^[^@\s]+@[^@\s]+\.[^@\s]+$/.test(email) && !busy
  const run = async () => {
    if (!canRun) return
    setBusy(true)
    await emailExport(email)
    setBusy(false)
  }

  return (
    <Modal open={open} onClose={close} title="이메일로 내보내기" className="w-[440px] max-w-[92vw]">
      <div className="text-[15px] font-bold">이메일로 내보내기</div>
      <p className="mt-2 text-[12.5px] leading-[1.6] text-muted">
        암호화된 금고 번들을 입력한 이메일로 보내드려요. 먼저{' '}
        <span className="font-mono text-fg-soft">확인 링크</span>가 담긴 메일이 가고, 그 링크를
        눌러야 실제 파일이 담긴 메일이 한 번 더 발송됩니다.
      </p>
      <input
        type="email"
        value={email}
        onChange={(e) => setEmail(e.target.value)}
        onKeyDown={(e) => {
          if (e.key === 'Enter' && canRun) void run()
        }}
        placeholder="목적지 이메일 주소"
        autoFocus
        className="mt-[14px] w-full rounded-lg border border-border bg-surface px-3 py-[10px] text-[12.5px] text-fg outline-none focus:border-[rgba(62,207,142,.55)]"
      />
      <div className="mt-[18px] flex justify-end gap-2">
        <button
          type="button"
          onClick={close}
          className="cursor-pointer rounded-lg border border-border bg-none px-[14px] py-2 text-[12.5px] font-semibold text-muted hover:border-border-strong hover:text-fg-soft"
        >
          취소
        </button>
        <button
          type="button"
          onClick={() => void run()}
          disabled={!canRun}
          className="rounded-lg border-none px-[14px] py-2 text-[12.5px] font-bold hover:brightness-[1.07]"
          style={{
            background: canRun ? '#3ECF8E' : '#1B2128',
            color: canRun ? '#05231A' : '#525B67',
            cursor: canRun ? 'pointer' : 'not-allowed',
          }}
        >
          {busy ? '요청 중…' : '확인 메일 보내기'}
        </button>
      </div>
    </Modal>
  )
}
```

- [ ] **Step 8: `App.tsx`에 모달 연결**

`frontend/src/App.tsx:19`의 import를 다음으로 교체:
```typescript
import { DeleteModal, DupModal, EmailSyncModal, EnvModal, RotateModal, SyncModal } from '@/components/modals/Modals'
```
`frontend/src/App.tsx:94`(`<SyncModal />` 바로 뒤)에 추가:
```typescript
      <EmailSyncModal />
```

- [ ] **Step 9: `VaultScreen.tsx`에 버튼 추가**

`frontend/src/components/screens/VaultScreen.tsx` 상단 import에 추가:
```typescript
import { syncRelayConfigured } from '@/lib/syncRelay'
```
"가져오기" 버튼(`onClick={s.openSync}`) 바로 뒤에 추가:
```tsx
        {syncRelayConfigured && (
          <button
            type="button"
            onClick={s.openEmailSync}
            title="암호화된 금고를 이메일로 다른 기기에 전달"
            className="cursor-pointer rounded-lg border border-border bg-surface px-3 py-[9px] text-[11.5px] font-semibold text-muted hover:border-border-strong hover:text-fg-soft"
          >
            이메일로 내보내기
          </button>
        )}
```

- [ ] **Step 10: 루트 `.env.example`에 안내 추가**

`.env.example`의 `VITE_API_BASE=...` 줄 뒤에 추가:
```text

# --- SYNC-2(재설계): 이메일 릴레이 동기화(계정/DB 없음, 옵트인) ---
# manager-relay/ 를 직접 배포한 뒤 그 공개 주소를 넣는다(비밀 아님 — 자격증명은
# manager-relay 자신의 배포 환경에만 있음). 비워두면 "이메일로 내보내기" 버튼이 안 보인다.
VITE_SYNC_RELAY_URL=
```

- [ ] **Step 11: 타입체크·린트·빌드 검증**

Run(작업 디렉토리 `frontend/`):
```bash
npx tsc --noEmit
npm run lint
npm run build
```
Expected: 셋 다 에러 없이 통과.

- [ ] **Step 12: 수동 브라우저 확인**

1. `manager-relay/`에서 더미 SMTP env로 로컬 서버 기동(`python -m app.main`, 포트 8090).
   (실제 메일 발송까지 확인하려면 진짜 SMTP 자격증명으로 교체 — 이건 자동화 범위 밖, 사람이 확인)
2. `frontend/.env.local`에 `VITE_SYNC_RELAY_URL=http://localhost:8090` 추가.
3. `npm run dev`로 프론트 기동, 백엔드(`backend/`)도 별도로 기동.
4. 보관함 화면에서 "이메일로 내보내기" 버튼이 보이는지, 클릭 시 모달이 뜨는지, 이메일 형식이
   아니면 버튼이 비활성인지, 제출 시 네트워크 탭에 `POST /sync/request`가 200으로 잡히는지 확인.
5. `VITE_SYNC_RELAY_URL`을 지우고 재기동 → 버튼이 사라지는지 확인.

- [ ] **Step 13: 커밋**

```bash
git add frontend/src/lib/syncRelay.ts frontend/src/store/keylensStore.ts \
  frontend/src/components/modals/Modals.tsx frontend/src/App.tsx \
  frontend/src/components/screens/VaultScreen.tsx .env.example
git commit -m "$(cat <<'EOF'
feat(frontend): SYNC-2 재설계 — 이메일로 내보내기 UI(계정/DB 없음)

manager-relay POST /sync/request 를 호출하는 새 모달. VITE_SYNC_RELAY_URL
미설정 시 버튼 자체가 안 보여 "되는 척" 하지 않는다.

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
EOF
)"
```

---

### Task 6: CI에 `manager-relay` 테스트 추가

**Files:**
- Modify: `.github/workflows/ci.yml`

**Interfaces:**
- Consumes: `manager-relay/requirements-dev.txt`, `manager-relay/pytest.ini`(Task 1~4에서 이미
  존재).
- Produces: 없음(CI 설정 변경만).

- [ ] **Step 1: `backend-test` 잡 바로 뒤에 새 잡 추가**

`.github/workflows/ci.yml`의 `backend-test:` 잡 블록이 끝나는 지점(`frontend:` 잡 시작 직전)에
아래 잡을 추가:
```yaml
  manager-relay-test:
    name: 매니저 릴레이 테스트 (pytest)
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.13"
      - name: 의존성 설치(런타임+테스트)
        run: pip install -r manager-relay/requirements-dev.txt
      - name: pytest
        working-directory: manager-relay
        env:
          SMTP_HOST: smtp.test.invalid
          SMTP_PORT: "587"
          SMTP_USER: relay@test.invalid
          SMTP_PASS: test-password
          PUBLIC_BASE_URL: http://localhost:8080
        run: python -m pytest -q
```

- [ ] **Step 2: 로컬에서 YAML 문법 확인**

Run: `python -c "import yaml, sys; yaml.safe_load(open('.github/workflows/ci.yml', encoding='utf-8'))"`
Expected: 에러 없이 종료(파이썬에 PyYAML이 없으면 `pip install pyyaml` 후 재시도 — 이미
`backend/requirements.txt`에 있으므로 backend venv 안에서 실행해도 됨).

- [ ] **Step 3: 커밋**

```bash
git add .github/workflows/ci.yml
git commit -m "$(cat <<'EOF'
ci: manager-relay pytest 잡 추가

backend-test 와 동일한 패턴 — push/PR 마다 manager-relay 테스트도
자동 실행되게 한다.

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
EOF
)"
```

---

### Task 7: 문서 동기화 — BACKLOG.md + 결정 메모

**Files:**
- Modify: `docs/BACKLOG.md:369-388`(SYNC-2 항목 전체 재작성)
- Modify: `docs/memo/2026-07-30-sync2-server-sync-decisions.md`(대체됐음을 알리는 안내 추가)

**Interfaces:** 없음(문서 전용, 코드 인터페이스 없음)

- [ ] **Step 1: `docs/BACKLOG.md`의 SYNC-2 항목(369~388줄) 전체를 아래로 교체**

```markdown
### SYNC-2 ✅ 이메일 릴레이 기반 동기화 (계정·DB 없음)
- **중요도**: 🟡 Medium | **의존성**: SYNC-0(번들 포맷 재사용) | **사이즈**: M
- **배경**: 최초 설계(Supabase 계정 로그인)는 이메일 발송 한도(프로젝트 전체 시간당 2통)와
  오픈소스 대회에서의 "우리가 클라우드 DB를 운영한다"는 인상 문제로 폐기했다. 대신 계정·DB
  없이 **SMTP로만** 목적지 이메일로 암호문 번들을 전달하는 방식으로 재설계했다.
- **설계 문서**: `docs/superpowers/specs/2026-08-26-sync2-email-relay-design.md`(구 결정 메모
  `docs/memo/2026-07-30-sync2-server-sync-decisions.md`를 대체).
- **핵심 설계**
  - [x] **계정·DB 없음**: `manager-relay/`(독립 배포 서비스)가 SMTP 자격증명만 자기 env로 쥐고,
    번들·이메일 주소를 영구 저장하지 않음(메모리 + TTL 15분만).
  - [x] **2단계 발송(어뷰징 방지)**: 확인 메일(첨부 없음) → 링크 클릭 → 실제 첨부 메일. 임의
    주소로 스팸을 보내는 걸 막음.
  - [x] **셀프호스트 가능**: 코드는 공개, 실행은 각 운영자("매니저")가 자기 SMTP 자격증명으로
    직접 배포. `@supabase/supabase-js` 같은 신규 런타임 의존성 0(표준 라이브러리 `smtplib`).
  - [x] **복원은 기존 SYNC-0 그대로**: 새 복호화 경로 없음 — 첨부파일을 기존 "가져오기" 화면에
    넣으면 끝.
- **테스트 체크리스트**
  - [x] 🧪 토큰 발급/조회/소진/TTL 만료(`manager-relay/tests/test_token_store.py`)
  - [x] 🧪 dest_email/IP별 요율 제한(`manager-relay/tests/test_rate_limit.py`)
  - [x] 🧪 SMTP 발송 성공/실패 정규화(`manager-relay/tests/test_mailer.py`)
  - [x] 🧪 `/sync/request` → `/sync/confirm` 엔드투엔드, 429/410/502 상태코드
    (`manager-relay/tests/test_main.py`)
  - [ ] 🧪 실제 SMTP 자격증명으로 왕복(수동 검증 — CI에 진짜 자격증명을 두지 않으므로 사람이 확인)
- **범위 밖**: 매니저 릴레이의 영구 저장소, Gmail API/OAuth 경로, 여러 매니저 간 페더레이션.
```

- [ ] **Step 2: 구 결정 메모 상단에 대체 안내 추가**

`docs/memo/2026-07-30-sync2-server-sync-decisions.md`의 첫 번째 `>` 인용구 블록 바로 뒤에 추가:
```markdown
> **⚠️ 2026-08-26 대체됨**: 이 문서의 Supabase 계정 로그인 설계는 이메일 발송 한도·오픈소스
> 대회 정합성 문제로 폐기됐다. 새 설계는
> `docs/superpowers/specs/2026-08-26-sync2-email-relay-design.md`(계정·DB 없는 SMTP 릴레이)를
> 참고 — 이 문서는 "왜 처음엔 Supabase를 골랐었는지"의 역사적 기록으로만 남긴다.
```

- [ ] **Step 3: 커밋**

```bash
git add docs/BACKLOG.md docs/memo/2026-07-30-sync2-server-sync-decisions.md
git commit -m "$(cat <<'EOF'
docs: SYNC-2 백로그·결정 메모를 이메일 릴레이 설계로 갱신

Supabase 계정 로그인 방식은 폐기, 구현 완료된 이메일 릴레이 설계로
BACKLOG 항목을 재작성. 구 결정 메모는 대체 안내만 추가하고 보존.

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
EOF
)"
```
