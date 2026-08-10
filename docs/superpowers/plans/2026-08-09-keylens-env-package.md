<!--
SPDX-FileCopyrightText: 2026 [Your Name]
SPDX-License-Identifier: MIT
-->

# `keylens-env` 패키지 + 프론트 프로젝트 접근 설정 화면 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** RUNTIME-1의 남은 두 서브플랜을 완성한다 — (1) 실제로 `import keylens_env`해서 `load_env()`로
KeyLens 금고 값을 `os.environ`에 주입하는 독립 Python 패키지, (2) 프론트에 프로젝트별 허용 디렉토리를
미리 등록해 두는 "프로젝트 접근" 설정 화면. 설계는
`docs/superpowers/specs/2026-08-09-keylens-env-package-design.md`에서 확정됨.

**Architecture:** 백엔드(`/sdk/env`, `/sdk/projects*`)는 이미 완성돼 있어 이 플랜은 백엔드 코드를 전혀
건드리지 않는다. (1) `keylens-env/`는 레포 루트의 독립 Python 패키지 — `config.py`(`.keylens.toml`
상위 탐색, 표준 `tomllib`), `client.py`(표준 `urllib.request`로 HTTP, 상태코드→예외 매핑),
`exceptions.py`(타입 예외 계층), `__init__.py`(`load_env()` 공개 API)로 나뉜다. 새 런타임 의존성 0 —
빌드 도구 `setuptools`만 dev 의존성으로 추가(license-auditor 확인: hatchling은 전이 의존성
`pathspec`이 MPL-2.0이라 기각, setuptools는 카피레프트 전이 의존성 없음). (2) 프론트는 기존
`sdkApi`(승인 대기 전용)를 프로젝트/디렉토리 CRUD로 확장하고, 새 `ProjectAccessScreen`을 4번째
사이드바 메뉴로 추가한다.

**Tech Stack:** Python 3.11+(표준 라이브러리 `urllib.request`·`tomllib`만, 새 런타임 의존성 0) /
`setuptools`(빌드 전용 dev 의존성) / React 19 + TypeScript + Zustand(프론트, 기존 스택 재사용).

## Global Constraints

- `keylens-env` 패키지는 **새 런타임 의존성을 추가하지 않는다** — `urllib.request`·`tomllib`(둘 다
  표준 라이브러리)만 쓴다. 빌드 백엔드는 `setuptools`(PSF/BSD 계열, 전이 의존성에 카피레프트 없음 —
  license-auditor 확인 완료. **hatchling은 쓰지 않는다** — 전이 의존성 `pathspec`이 MPL-2.0).
- `keylens-env`는 **`backend/` 코드를 import하지 않는다** — 순수 HTTP 클라이언트로 남는다(통합
  테스트 1개만 예외적으로 `backend.app.main:app`을 실제 서버로 띄워 검증, 이건 테스트 전용 요구사항).
<!-- REUSE-IgnoreStart -->
- 모든 새 파일 맨 위에 SPDX 헤더 2줄: 파이썬은 `# SPDX-FileCopyrightText: 2026 [Your Name]` /
  `# SPDX-License-Identifier: MIT`, TS/TSX·마크다운은 각 언어 관례(TS는 `//`, MD는 HTML 주석).
<!-- REUSE-IgnoreEnd -->
- `load_env()`는 승인 대기(403)에서 **폴링하지 않는다** — 즉시 타입이 다른 예외를 던지고 끝난다
  (설계의 핵심 판단, `docs/superpowers/specs/2026-08-09-keylens-env-package-design.md` 참고).
- 조용한 실패·빈 값 반환은 절대 없다 — 실패는 항상 `KeylensEnvError` 계열 예외로 표면화한다.
- 프론트는 기존 관례를 그대로 따른다: `vaultApi`와 같은 패턴의 `sdkApi` 확장, `vaultErrorText`/
  `showToast` 에러 처리, snake_case API 계약(`api/types.ts`) ↔ camelCase 프론트 타입(`types.ts`)
  분리, React 컴포넌트/스토어 자동테스트 없음(수동 브라우저 확인 — 이 프로젝트의 기존 관례).
- 실제 PyPI 업로드는 이 플랜 범위 밖(로컬 editable install까지만) — 커밋 메시지 끝에
  `Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>`.

---

### Task 1: `keylens-env` 패키지 스캐폴딩 + 예외 계층

**Files:**
- Create: `keylens-env/pyproject.toml`
- Create: `keylens-env/README.md` (Task 5에서 전체 내용으로 교체 — 여기선 최소 스텁)
- Create: `keylens-env/src/keylens_env/__init__.py` (최소 — `load_env()`는 Task 4에서 추가)
- Create: `keylens-env/src/keylens_env/exceptions.py`
- Test: `keylens-env/tests/test_exceptions.py`

**Interfaces:**
- Consumes: 없음(신규 패키지)
- Produces (Task 2/3/4가 그대로 씀):
  - `keylens_env.exceptions.KeylensEnvError`(베이스)
  - `keylens_env.exceptions.KeylensNotRunningError`
  - `keylens_env.exceptions.KeylensLockedError`
  - `keylens_env.exceptions.KeylensApprovalPendingError`
  - `keylens_env.exceptions.KeylensConfigError`
  - `keylens_env.exceptions.KeylensServerError`

- [ ] **Step 1: `keylens-env/pyproject.toml` 생성**

```toml
[build-system]
requires = ["setuptools>=68"]
build-backend = "setuptools.build_meta"

[project]
name = "keylens-env"
version = "0.1.0"
description = "Local-first runtime secrets loader for KeyLens — a dotenv-style API backed by the KeyLens vault."
readme = "README.md"
requires-python = ">=3.11"
license = { text = "MIT" }
authors = [{ name = "[Your Name]" }]
dependencies = []

[project.optional-dependencies]
test = ["pytest>=9.0.3"]

[tool.setuptools.packages.find]
where = ["src"]
```

- [ ] **Step 2: `keylens-env/README.md` 최소 스텁 생성**

```markdown
<!--
SPDX-FileCopyrightText: 2026 [Your Name]
SPDX-License-Identifier: MIT
-->
# keylens-env

(작업 중 — Task 5에서 전체 사용법으로 채워집니다.)
```

- [ ] **Step 3: `keylens-env/src/keylens_env/__init__.py` 최소본 생성**

```python
# SPDX-FileCopyrightText: 2026 [Your Name]
# SPDX-License-Identifier: MIT
"""keylens-env — dotenv 대체 런타임 SDK(작업 중, load_env()는 Task 4에서 추가)."""
from __future__ import annotations

__version__ = "0.1.0"
```

- [ ] **Step 4: 편집 가능(editable) 설치**

Run: `cd backend && .venv/Scripts/pip.exe install -e ../keylens-env`
Expected: `Successfully installed keylens-env-0.1.0`

- [ ] **Step 5: 임포트 확인**

Run: `cd backend && .venv/Scripts/python.exe -c "import keylens_env; print(keylens_env.__version__)"`
Expected: `0.1.0`

- [ ] **Step 6: 실패하는 테스트 작성 — `keylens-env/tests/test_exceptions.py`**

```python
# SPDX-FileCopyrightText: 2026 [Your Name]
# SPDX-License-Identifier: MIT
"""예외 계층 — 전부 KeylensEnvError를 상속해 한 번에 잡을 수 있어야 한다."""
import pytest

from keylens_env.exceptions import (
    KeylensApprovalPendingError,
    KeylensConfigError,
    KeylensEnvError,
    KeylensLockedError,
    KeylensNotRunningError,
    KeylensServerError,
)


@pytest.mark.parametrize(
    "exc_cls",
    [
        KeylensNotRunningError,
        KeylensLockedError,
        KeylensApprovalPendingError,
        KeylensConfigError,
        KeylensServerError,
    ],
)
def test_specific_exceptions_are_keylens_env_error(exc_cls):
    assert issubclass(exc_cls, KeylensEnvError)


def test_keylens_env_error_is_exception():
    assert issubclass(KeylensEnvError, Exception)


def test_exceptions_carry_message():
    err = KeylensLockedError("금고가 잠겨 있어요")
    assert str(err) == "금고가 잠겨 있어요"
```

- [ ] **Step 7: 테스트 실행 → 실패 확인**

Run: `cd backend && .venv/Scripts/python.exe -m pytest ../keylens-env/tests/test_exceptions.py -v`
Expected: `ModuleNotFoundError: No module named 'keylens_env.exceptions'`

- [ ] **Step 8: `keylens-env/src/keylens_env/exceptions.py` 생성**

```python
# SPDX-FileCopyrightText: 2026 [Your Name]
# SPDX-License-Identifier: MIT
"""keylens-env 예외 계층.

전부 KeylensEnvError를 상속하므로 `except KeylensEnvError`로 한 번에 잡을 수도 있고,
필요하면 구체적인 타입으로 구분해서 잡을 수도 있다. 조용한 실패·빈 값 반환은 절대
하지 않는다 — 실패는 항상 이 계층의 예외로 표면화된다.
"""
from __future__ import annotations


class KeylensEnvError(Exception):
    """모든 keylens-env 예외의 베이스."""


class KeylensNotRunningError(KeylensEnvError):
    """KeyLens 앱에 연결할 수 없음(꺼져 있거나 접속 주소가 다름)."""


class KeylensLockedError(KeylensEnvError):
    """KeyLens 금고가 잠겨 있음(401)."""


class KeylensApprovalPendingError(KeylensEnvError):
    """이 디렉토리의 접근 요청이 KeyLens에서 아직 승인되지 않음(403)."""


class KeylensConfigError(KeylensEnvError):
    """`.keylens.toml`을 찾지 못했거나 형식이 잘못됨, 혹은 project 인자도 없음."""


class KeylensServerError(KeylensEnvError):
    """KeyLens가 예상치 못한 응답을 반환함(401/403이 아닌 다른 오류 상태)."""
```

- [ ] **Step 9: 테스트 실행 → 통과 확인**

Run: `cd backend && .venv/Scripts/python.exe -m pytest ../keylens-env/tests/test_exceptions.py -v`
Expected: `7 passed`

- [ ] **Step 10: 커밋**

```bash
git add keylens-env/pyproject.toml keylens-env/README.md keylens-env/src/keylens_env/__init__.py keylens-env/src/keylens_env/exceptions.py keylens-env/tests/test_exceptions.py
git commit -m "feat(keylens-env): 패키지 스캐폴딩 + 예외 계층(setuptools, 새 런타임 의존성 0)

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>"
```

---

### Task 2: `config.py` — `.keylens.toml` 상위 탐색

**Files:**
- Create: `keylens-env/src/keylens_env/config.py`
- Test: `keylens-env/tests/test_config.py`

**Interfaces:**
- Consumes: `keylens_env.exceptions.KeylensConfigError`(Task 1)
- Produces (Task 4가 그대로 씀):
  - `keylens_env.config.find_config(start: Path | None = None) -> tuple[str, Path]` — `(project, config_dir)`

- [ ] **Step 1: 실패하는 테스트 작성 — `keylens-env/tests/test_config.py`**

```python
# SPDX-FileCopyrightText: 2026 [Your Name]
# SPDX-License-Identifier: MIT
"""config.py — .keylens.toml 상위 탐색(python-dotenv의 find_dotenv()와 같은 방식)."""
import pytest

from keylens_env.config import find_config
from keylens_env.exceptions import KeylensConfigError


def test_find_config_in_start_dir(tmp_path):
    (tmp_path / ".keylens.toml").write_text('project = "블로그"\n', encoding="utf-8")
    project, config_dir = find_config(tmp_path)
    assert project == "블로그"
    assert config_dir == tmp_path


def test_find_config_searches_upward(tmp_path):
    (tmp_path / ".keylens.toml").write_text('project = "블로그"\n', encoding="utf-8")
    nested = tmp_path / "a" / "b" / "c"
    nested.mkdir(parents=True)
    project, config_dir = find_config(nested)
    assert project == "블로그"
    assert config_dir == tmp_path


def test_find_config_not_found_raises(tmp_path):
    empty = tmp_path / "no-config-here"
    empty.mkdir()
    with pytest.raises(KeylensConfigError):
        find_config(empty)


def test_find_config_missing_project_key_raises(tmp_path):
    (tmp_path / ".keylens.toml").write_text('other_key = "값"\n', encoding="utf-8")
    with pytest.raises(KeylensConfigError):
        find_config(tmp_path)


def test_find_config_malformed_toml_raises(tmp_path):
    (tmp_path / ".keylens.toml").write_text("이건 toml이 아님 {{{\n", encoding="utf-8")
    with pytest.raises(KeylensConfigError):
        find_config(tmp_path)


def test_find_config_blank_project_value_raises(tmp_path):
    (tmp_path / ".keylens.toml").write_text('project = "   "\n', encoding="utf-8")
    with pytest.raises(KeylensConfigError):
        find_config(tmp_path)
```

- [ ] **Step 2: 테스트 실행 → 실패 확인**

Run: `cd backend && .venv/Scripts/python.exe -m pytest ../keylens-env/tests/test_config.py -v`
Expected: `ModuleNotFoundError: No module named 'keylens_env.config'`

- [ ] **Step 3: `keylens-env/src/keylens_env/config.py` 생성**

```python
# SPDX-FileCopyrightText: 2026 [Your Name]
# SPDX-License-Identifier: MIT
"""`.keylens.toml` 탐색 — python-dotenv의 find_dotenv()와 같은 방식으로 cwd(또는 지정한
시작 디렉토리)에서 상위로 올라가며 찾는다. 파일시스템 루트에 닿으면 중단한다.
"""
from __future__ import annotations

import tomllib
from pathlib import Path

from .exceptions import KeylensConfigError

CONFIG_FILENAME = ".keylens.toml"


def find_config(start: Path | None = None) -> tuple[str, Path]:
    """start(기본 Path.cwd())에서 상위로 .keylens.toml을 탐색해 (project, config_dir)을 반환한다.

    config_dir은 .keylens.toml이 실제로 위치한 디렉토리 — SDK 요청의 path 파라미터로 쓰인다
    (탐색을 시작한 start가 아니라, 실제로 찾은 위치가 프로젝트 루트이므로).
    """
    current = (start or Path.cwd()).resolve()
    for directory in [current, *current.parents]:
        candidate = directory / CONFIG_FILENAME
        if candidate.is_file():
            return _read_project(candidate), directory
    raise KeylensConfigError(
        f"{CONFIG_FILENAME}을(를) 찾을 수 없어요 — 프로젝트 루트에 만들거나 "
        "load_env(project=...)로 직접 지정하세요"
    )


def _read_project(path: Path) -> str:
    try:
        data = tomllib.loads(path.read_text(encoding="utf-8"))
    except tomllib.TOMLDecodeError as e:
        raise KeylensConfigError(f"{path}이(가) 올바른 TOML 형식이 아니에요: {e}") from e
    project = data.get("project")
    if not isinstance(project, str) or not project.strip():
        raise KeylensConfigError(f'{path}에 project 키가 없어요 — project = "이름" 을 추가하세요')
    return project
```

- [ ] **Step 4: 테스트 실행 → 통과 확인**

Run: `cd backend && .venv/Scripts/python.exe -m pytest ../keylens-env/tests/test_config.py -v`
Expected: `6 passed`

- [ ] **Step 5: 커밋**

```bash
git add keylens-env/src/keylens_env/config.py keylens-env/tests/test_config.py
git commit -m "feat(keylens-env): config.py — .keylens.toml 상위 탐색(python-dotenv 방식)

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>"
```

---

### Task 3: `client.py` — HTTP 클라이언트 + 예외 매핑

**Files:**
- Create: `keylens-env/src/keylens_env/client.py`
- Test: `keylens-env/tests/test_client.py`

**Interfaces:**
- Consumes: `keylens_env.exceptions.*`(Task 1)
- Produces (Task 4가 그대로 씀):
  - `keylens_env.client.DEFAULT_BASE_URL: str`(`"http://127.0.0.1:8765"`)
  - `keylens_env.client.fetch_env(project: str, path: str, base_url: str = DEFAULT_BASE_URL) -> dict[str, str]`

- [ ] **Step 1: 실패하는 테스트 작성 — `keylens-env/tests/test_client.py`**

```python
# SPDX-FileCopyrightText: 2026 [Your Name]
# SPDX-License-Identifier: MIT
"""client.py — 표준 라이브러리 http.server로 가짜 KeyLens 서버를 흉내 내 상태코드→예외 매핑을 검증."""
import json
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

import pytest

from keylens_env import client
from keylens_env.exceptions import (
    KeylensApprovalPendingError,
    KeylensLockedError,
    KeylensNotRunningError,
    KeylensServerError,
)


class _Handler(BaseHTTPRequestHandler):
    status_code = 200
    body: dict = {"values": {"OPENAI_API_KEY": "sk-dummy"}}

    def do_POST(self):  # noqa: N802 - http.server 관례 메서드명
        length = int(self.headers.get("Content-Length", 0))
        self.rfile.read(length)
        self.send_response(self.status_code)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps(self.body).encode("utf-8"))

    def log_message(self, format, *args):  # noqa: A002 - 테스트 출력 조용히
        pass


@pytest.fixture
def fake_server():
    server = HTTPServer(("127.0.0.1", 0), _Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield server
    server.shutdown()
    thread.join(timeout=2)


def _base_url(server: HTTPServer) -> str:
    return f"http://127.0.0.1:{server.server_port}"


def test_fetch_env_success(fake_server):
    _Handler.status_code = 200
    _Handler.body = {"values": {"OPENAI_API_KEY": "sk-dummy"}}
    values = client.fetch_env("블로그", "/repo/blog", base_url=_base_url(fake_server))
    assert values == {"OPENAI_API_KEY": "sk-dummy"}


def test_fetch_env_locked_raises(fake_server):
    _Handler.status_code = 401
    _Handler.body = {"detail": "잠김"}
    with pytest.raises(KeylensLockedError):
        client.fetch_env("블로그", "/repo/blog", base_url=_base_url(fake_server))


def test_fetch_env_approval_pending_raises(fake_server):
    _Handler.status_code = 403
    _Handler.body = {"detail": "승인 대기"}
    with pytest.raises(KeylensApprovalPendingError):
        client.fetch_env("블로그", "/repo/blog", base_url=_base_url(fake_server))


def test_fetch_env_unexpected_status_raises_server_error(fake_server):
    _Handler.status_code = 422
    _Handler.body = {"detail": "복호화 실패"}
    with pytest.raises(KeylensServerError):
        client.fetch_env("블로그", "/repo/blog", base_url=_base_url(fake_server))


def test_fetch_env_connection_refused_raises_not_running():
    with pytest.raises(KeylensNotRunningError):
        client.fetch_env("블로그", "/repo/blog", base_url="http://127.0.0.1:1")
```

- [ ] **Step 2: 테스트 실행 → 실패 확인**

Run: `cd backend && .venv/Scripts/python.exe -m pytest ../keylens-env/tests/test_client.py -v`
Expected: `ModuleNotFoundError: No module named 'keylens_env.client'`

- [ ] **Step 3: `keylens-env/src/keylens_env/client.py` 생성**

```python
# SPDX-FileCopyrightText: 2026 [Your Name]
# SPDX-License-Identifier: MIT
"""KeyLens 로컬 백엔드로 HTTP 호출 — 표준 라이브러리 urllib.request만 쓴다(새 의존성 0).

상태 코드 → 예외 매핑은 이 파일 한 곳에서만 한다 — 백엔드가 상태 코드를 바꾸면 여기만 고치면 된다.
"""
from __future__ import annotations

import json
import urllib.error
import urllib.request

from .exceptions import (
    KeylensApprovalPendingError,
    KeylensLockedError,
    KeylensNotRunningError,
    KeylensServerError,
)

DEFAULT_BASE_URL = "http://127.0.0.1:8765"
_TIMEOUT_SECONDS = 5.0


def fetch_env(project: str, path: str, base_url: str = DEFAULT_BASE_URL) -> dict[str, str]:
    """POST {base_url}/sdk/env — 성공 시 {official_env_name: value} 딕셔너리를 반환한다.

    실패는 절대 조용히 넘어가지 않고 타입이 다른 예외로 정규화한다:
    - 연결 자체가 안 됨(KeyLens 꺼짐/주소 다름) → KeylensNotRunningError
    - 401(잠김) → KeylensLockedError
    - 403(미승인) → KeylensApprovalPendingError
    - 그 외 오류 상태(예: 422 복호화 실패) → KeylensServerError
    """
    body = json.dumps({"project": project, "path": path}).encode("utf-8")
    req = urllib.request.Request(
        f"{base_url}/sdk/env",
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=_TIMEOUT_SECONDS) as res:
            payload = json.loads(res.read().decode("utf-8"))
            return payload["values"]
    except urllib.error.HTTPError as e:
        if e.code == 401:
            raise KeylensLockedError(
                "KeyLens 금고가 잠겨 있어요 — KeyLens 앱에서 잠금을 해제하세요"
            ) from None
        if e.code == 403:
            raise KeylensApprovalPendingError(
                f"'{path}'가 '{project}' 프로젝트 키를 요청했어요 — "
                "KeyLens 앱의 '승인 대기' 화면에서 허용해 주세요"
            ) from None
        raise KeylensServerError(
            f"KeyLens가 예상치 못한 응답을 반환했어요(HTTP {e.code})"
        ) from None
    except (urllib.error.URLError, OSError, TimeoutError):
        raise KeylensNotRunningError(
            f"{base_url}에서 KeyLens를 찾을 수 없어요 — KeyLens 앱을 켜고 잠금을 해제하세요"
        ) from None
```

- [ ] **Step 4: 테스트 실행 → 통과 확인**

Run: `cd backend && .venv/Scripts/python.exe -m pytest ../keylens-env/tests/test_client.py -v`
Expected: `5 passed`

- [ ] **Step 5: 커밋**

```bash
git add keylens-env/src/keylens_env/client.py keylens-env/tests/test_client.py
git commit -m "feat(keylens-env): client.py — urllib 기반 HTTP 클라이언트 + 상태코드 예외 매핑

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>"
```

---

### Task 4: `load_env()` 공개 API

**Files:**
- Modify: `keylens-env/src/keylens_env/__init__.py`
- Test: `keylens-env/tests/test_load_env.py`

**Interfaces:**
- Consumes: `keylens_env.config.find_config`(Task 2), `keylens_env.client.fetch_env`/`DEFAULT_BASE_URL`(Task 3), `keylens_env.exceptions.*`(Task 1)
- Produces (Task 5의 통합 테스트·README가 그대로 씀):
  - `keylens_env.load_env(project: str | None = None) -> None`
  - `keylens_env.KeylensEnvError` 등 예외 전부 최상위에서 재노출

- [ ] **Step 1: 실패하는 테스트 작성 — `keylens-env/tests/test_load_env.py`**

```python
# SPDX-FileCopyrightText: 2026 [Your Name]
# SPDX-License-Identifier: MIT
"""load_env() — config.py/client.py를 엮는 공개 API. 둘 다 monkeypatch로 대체해
네트워크·파일시스템 없이 조합 로직만 검증한다(실제 왕복 검증은 Task 5의 통합 테스트)."""
from pathlib import Path

import pytest

import keylens_env
from keylens_env.exceptions import KeylensLockedError


def test_load_env_uses_config_when_project_not_given(monkeypatch):
    monkeypatch.setattr(keylens_env, "find_config", lambda: ("블로그", Path("/repo/blog")))
    captured = {}

    def fake_fetch_env(project, path, base_url):
        captured["args"] = (project, path, base_url)
        return {"OPENAI_API_KEY": "sk-dummy"}

    monkeypatch.setattr(keylens_env, "fetch_env", fake_fetch_env)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)

    keylens_env.load_env()

    assert captured["args"][0] == "블로그"
    assert captured["args"][1] == str(Path("/repo/blog"))
    assert __import__("os").environ["OPENAI_API_KEY"] == "sk-dummy"


def test_load_env_explicit_project_skips_config(monkeypatch):
    def fail_if_called():
        raise AssertionError("project가 명시되면 find_config가 호출되면 안 됨")

    monkeypatch.setattr(keylens_env, "find_config", fail_if_called)
    captured = {}

    def fake_fetch_env(project, path, base_url):
        captured["project"] = project
        return {}

    monkeypatch.setattr(keylens_env, "fetch_env", fake_fetch_env)

    keylens_env.load_env(project="사이드")

    assert captured["project"] == "사이드"


def test_load_env_propagates_typed_exception(monkeypatch):
    monkeypatch.setattr(keylens_env, "find_config", lambda: ("블로그", Path(".")))

    def raise_locked(project, path, base_url):
        raise KeylensLockedError("잠김")

    monkeypatch.setattr(keylens_env, "fetch_env", raise_locked)

    with pytest.raises(KeylensLockedError):
        keylens_env.load_env()


def test_load_env_uses_env_var_base_url(monkeypatch):
    monkeypatch.setattr(keylens_env, "find_config", lambda: ("블로그", Path(".")))
    monkeypatch.setenv("KEYLENS_BASE_URL", "http://127.0.0.1:9999")
    captured = {}

    def fake_fetch_env(project, path, base_url):
        captured["base_url"] = base_url
        return {}

    monkeypatch.setattr(keylens_env, "fetch_env", fake_fetch_env)
    keylens_env.load_env()

    assert captured["base_url"] == "http://127.0.0.1:9999"


def test_load_env_defaults_base_url_when_env_var_unset(monkeypatch):
    monkeypatch.setattr(keylens_env, "find_config", lambda: ("블로그", Path(".")))
    monkeypatch.delenv("KEYLENS_BASE_URL", raising=False)
    captured = {}

    def fake_fetch_env(project, path, base_url):
        captured["base_url"] = base_url
        return {}

    monkeypatch.setattr(keylens_env, "fetch_env", fake_fetch_env)
    keylens_env.load_env()

    assert captured["base_url"] == keylens_env.client.DEFAULT_BASE_URL
```

- [ ] **Step 2: 테스트 실행 → 실패 확인**

Run: `cd backend && .venv/Scripts/python.exe -m pytest ../keylens-env/tests/test_load_env.py -v`
Expected: `AttributeError: module 'keylens_env' has no attribute 'load_env'`

- [ ] **Step 3: `keylens-env/src/keylens_env/__init__.py` 전체 교체**

```python
# SPDX-FileCopyrightText: 2026 [Your Name]
# SPDX-License-Identifier: MIT
"""keylens-env — dotenv 대체 런타임 SDK.

실행 중이고 잠금 해제된 KeyLens 로컬 백엔드에서 값을 받아 os.environ에 주입한다.
디스크에 평문 .env 파일을 남기지 않는다. 자체 암호화·인증 로직은 없다 — KeyLens 앱이
켜져 있고 잠금 해제된 상태에서만 동작한다.
"""
from __future__ import annotations

import os
from pathlib import Path

from . import client
from .client import DEFAULT_BASE_URL, fetch_env
from .config import find_config
from .exceptions import (
    KeylensApprovalPendingError,
    KeylensConfigError,
    KeylensEnvError,
    KeylensLockedError,
    KeylensNotRunningError,
    KeylensServerError,
)

__version__ = "0.1.0"

__all__ = [
    "load_env",
    "KeylensEnvError",
    "KeylensNotRunningError",
    "KeylensLockedError",
    "KeylensApprovalPendingError",
    "KeylensConfigError",
    "KeylensServerError",
]


def load_env(project: str | None = None) -> None:
    """KeyLens 금고에서 값을 받아 os.environ에 주입한다.

    project를 생략하면 cwd에서 상위로 .keylens.toml을 탐색해 project를 정한다
    (python-dotenv의 .env 탐색과 같은 방식). project를 명시하면 탐색을 건너뛰고
    cwd를 그대로 승인 경로(path)로 쓴다.

    실패 시 절대 조용히 넘어가지 않는다 — KeylensEnvError 계열 예외를 그대로 던진다.
    """
    if project is not None:
        resolved_project = project
        request_path = str(Path.cwd().resolve())
    else:
        resolved_project, config_dir = find_config()
        request_path = str(config_dir)

    base_url = os.environ.get("KEYLENS_BASE_URL", DEFAULT_BASE_URL)
    values = fetch_env(resolved_project, request_path, base_url=base_url)
    os.environ.update(values)
```

> `from . import client`를 남겨 두는 이유: 테스트가 `keylens_env.client.DEFAULT_BASE_URL`을 참조한다
> (`test_load_env_defaults_base_url_when_env_var_unset`). `fetch_env`/`find_config`는 각각
> `keylens_env.fetch_env`/`keylens_env.find_config`로 monkeypatch되므로 이 이름들로 직접 호출해야
> 테스트가 그 대체본을 실제로 타게 된다(모듈 경로로 다시 호출하면 패치가 무시된다).

- [ ] **Step 4: 테스트 실행 → 통과 확인**

Run: `cd backend && .venv/Scripts/python.exe -m pytest ../keylens-env/tests/test_load_env.py -v`
Expected: `5 passed`

- [ ] **Step 5: 전체 keylens-env 스위트 회귀 확인**

Run: `cd backend && .venv/Scripts/python.exe -m pytest ../keylens-env/tests -v --ignore=../keylens-env/tests/test_load_env_integration.py`
Expected: `18 passed`(Task 1: 7 + Task 2: 6 + Task 3: 5, `test_load_env_integration.py`는 아직 없으므로 `--ignore`는 무해)

- [ ] **Step 6: 커밋**

```bash
git add keylens-env/src/keylens_env/__init__.py keylens-env/tests/test_load_env.py
git commit -m "feat(keylens-env): load_env() 공개 API — config+client 조합, KEYLENS_BASE_URL 재정의

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>"
```

---

### Task 5: 실제 백엔드 통합 테스트 + README 완성

**Files:**
- Create: `keylens-env/tests/test_load_env_integration.py`
- Modify: `keylens-env/README.md` (Task 1의 스텁을 전체 내용으로 교체)

**Interfaces:**
- Consumes: `keylens_env.load_env`(Task 4), `backend.app.main:app`(기존, 이 테스트 파일만 예외적으로 import)
- Produces: 없음(이 플랜의 마지막 백엔드/패키지 검증 지점)

- [ ] **Step 1: `keylens-env/tests/test_load_env_integration.py` 생성**

```python
# SPDX-FileCopyrightText: 2026 [Your Name]
# SPDX-License-Identifier: MIT
"""keylens-env ↔ 실제 KeyLens 백엔드 end-to-end 검증(2개).

이 파일만 backend/ 의존성(fastapi, uvicorn 등)이 필요하다 — keylens_env 패키지 자체의
런타임 의존성이 아니라 이 레포 안에서 도는 테스트 전용 요구사항이다. keylens-env는
backend/ 코드를 import하지 않는다는 Global Constraint는 이 파일에는 적용되지 않는다
(테스트 전용 예외 — 계획의 Global Constraints 참고).

단독으로 실행한다(backend/tests/ 스위트와 같은 pytest 프로세스에서 함께 돌리지 않는다) —
app.main이 모듈 임포트 시점에 KEYLENS_VAULT_PATH를 읽어 VAULT 싱글턴을 구성하므로,
다른 테스트가 이미 app.main을 다른 경로로 임포트해 뒀으면 캐시된 모듈이 재사용되어
이 파일의 격리가 깨진다.
"""
from __future__ import annotations

import json
import socket
import sys
import threading
import time
import urllib.error
import urllib.request
from pathlib import Path
from urllib.parse import quote

import pytest

BACKEND_DIR = Path(__file__).resolve().parent.parent.parent / "backend"
sys.path.insert(0, str(BACKEND_DIR))

import keylens_env  # noqa: E402
from keylens_env.exceptions import KeylensLockedError  # noqa: E402

MASTER = "correct horse battery staple"
HOST = "127.0.0.1"


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind((HOST, 0))
        return s.getsockname()[1]


def _wait_ready(url: str, timeout: float = 10.0) -> bool:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            with urllib.request.urlopen(url, timeout=1.0) as r:
                if r.status == 200:
                    return True
        except (urllib.error.URLError, ConnectionError, OSError):
            time.sleep(0.1)
    return False


def _post(base_url: str, path: str, body: dict | None = None) -> dict:
    data = json.dumps(body).encode("utf-8") if body is not None else None
    req = urllib.request.Request(
        f"{base_url}{path}", data=data, headers={"Content-Type": "application/json"}, method="POST"
    )
    with urllib.request.urlopen(req, timeout=5) as r:
        return json.loads(r.read().decode("utf-8"))


@pytest.fixture
def live_backend(tmp_path, monkeypatch):
    """실제 app.main:app을 uvicorn으로 임시 포트에 기동(desktop/app.py의 _wait_ready 패턴과 동일)."""
    import uvicorn

    monkeypatch.setenv("KEYLENS_VAULT_PATH", str(tmp_path / "vault.db"))
    sys.modules.pop("app.main", None)  # 매 테스트마다 새 vault.db로 재구성되도록 재임포트
    from app.main import app

    port = _free_port()
    config = uvicorn.Config(app, host=HOST, port=port, log_level="warning")
    server = uvicorn.Server(config)
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    assert _wait_ready(f"http://{HOST}:{port}/health"), "테스트용 백엔드가 제때 기동하지 못했습니다"

    yield f"http://{HOST}:{port}"

    server.should_exit = True
    thread.join(timeout=5)


def test_load_env_end_to_end_against_real_backend(live_backend, monkeypatch, tmp_path):
    monkeypatch.setenv("KEYLENS_BASE_URL", live_backend)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)

    _post(live_backend, "/vault/init", {"password": MASTER})
    _post(
        live_backend,
        "/vault/entries",
        {
            "service": "openai", "kind": "api_key", "official_name": "OPENAI_API_KEY",
            "value": "sk-dummy", "project": "블로그",
        },
    )
    _post(live_backend, f"/sdk/projects/{quote('블로그')}/directories", {"path": str(tmp_path)})

    monkeypatch.chdir(tmp_path)
    (tmp_path / ".keylens.toml").write_text('project = "블로그"\n', encoding="utf-8")

    keylens_env.load_env()

    import os

    assert os.environ["OPENAI_API_KEY"] == "sk-dummy"


def test_load_env_raises_locked_when_vault_uninitialized(live_backend, monkeypatch, tmp_path):
    # 금고를 초기화하지 않은 상태 — sdk_env()는 초기화 여부와 무관하게 "잠김"과 동일하게 다룬다.
    monkeypatch.setenv("KEYLENS_BASE_URL", live_backend)
    monkeypatch.chdir(tmp_path)
    (tmp_path / ".keylens.toml").write_text('project = "블로그"\n', encoding="utf-8")

    with pytest.raises(KeylensLockedError):
        keylens_env.load_env()
```

- [ ] **Step 2: 테스트 실행 → 통과 확인**

Run: `cd backend && .venv/Scripts/python.exe -m pytest ../keylens-env/tests/test_load_env_integration.py -v`
Expected: `2 passed`(fastapi/uvicorn이 이미 backend/.venv에 설치돼 있으므로 추가 설치 불필요)

- [ ] **Step 3: `keylens-env/README.md` 전체 내용으로 교체**

```markdown
<!--
SPDX-FileCopyrightText: 2026 [Your Name]
SPDX-License-Identifier: MIT
-->
# keylens-env

**KeyLens** 금고에서 실행 중에 API 키를 받아오는 `dotenv` 대체 런타임 SDK입니다.
`.env` 파일을 디스크에 평문으로 남기지 않고, 실행 중이고 잠금 해제된 KeyLens 앱에서
그때그때 값을 받아 `os.environ`에 주입합니다.

## 전제조건

- KeyLens 앱(데스크톱 exe 또는 `python desktop/app.py`)이 **켜져 있고 잠금 해제된 상태**여야 합니다.
- Python 3.11 이상.

## 설치 (로컬 개발용)

```bash
pip install -e keylens-env/
```

(실제 PyPI 배포는 아직 하지 않았습니다 — 이 레포 안에서 개발 설치로만 씁니다.)

## 사용법

1. 소비 프로젝트 루트에 `.keylens.toml`을 만듭니다:

```toml
project = "블로그"
```

2. 코드에서:

```python
import keylens_env

keylens_env.load_env()  # os.environ에 주입, 실패 시 예외

import os
print(os.environ["OPENAI_API_KEY"])
```

`.keylens.toml` 없이 프로젝트를 직접 지정할 수도 있습니다:

```python
keylens_env.load_env(project="블로그")
```

## 접근 승인

`.keylens.toml`이 있는 디렉토리가 KeyLens에 **처음 요청**하면, KeyLens 앱에 승인 대기 알림이
뜹니다(KeyLens의 "프로젝트 접근" 화면에서 미리 등록해 둘 수도 있습니다 — 그러면 승인 팝업
없이 바로 통과합니다). 승인하기 전까지는 `KeylensApprovalPendingError`가 발생합니다 —
`load_env()`는 승인을 기다리지 않고 즉시 실패합니다. 승인 후 스크립트를 다시 실행하세요.

## 에러 처리

```python
import keylens_env

try:
    keylens_env.load_env()
except keylens_env.KeylensNotRunningError:
    print("KeyLens를 켜 주세요")
except keylens_env.KeylensLockedError:
    print("KeyLens 잠금을 해제해 주세요")
except keylens_env.KeylensApprovalPendingError:
    print("KeyLens에서 이 디렉토리의 접근 요청을 승인해 주세요")
except keylens_env.KeylensConfigError as e:
    print(f".keylens.toml 설정 문제: {e}")
```

또는 한 번에:

```python
except keylens_env.KeylensEnvError as e:
    print(f"KeyLens 연동 실패: {e}")
```

## 접속 주소 재정의

기본은 데스크톱 exe 포트(`http://127.0.0.1:8765`)입니다. 개발 모드(`node scripts/dev.mjs`,
포트 8003)에서 테스트하려면:

```bash
export KEYLENS_BASE_URL=http://127.0.0.1:8003   # Windows: set KEYLENS_BASE_URL=http://127.0.0.1:8003
```

## 보안 프레이밍

이 SDK가 새로운 신뢰 경계를 만드는 건 아닙니다 — 잠금 해제 상태에선 이미 로컬 프로세스가
KeyLens vault API를 호출할 수 있었습니다(기존 위협모델 그대로). 이 SDK가 실제로 추가하는
가치는 "전부 다 보임" 대신 **승인된 프로젝트 것만** 내려주는 최소 권한 스코핑입니다.

## 개발자용 — 테스트 실행

```bash
cd backend && .venv/Scripts/python.exe -m pytest ../keylens-env/tests -v
```

`test_load_env_integration.py`만 backend 의존성(fastapi·uvicorn)이 필요합니다 — 그 외
테스트는 keylens-env 자체 외에 아무것도 필요 없습니다.

## 라이선스

MIT — [../LICENSE](../LICENSE) 참고.
```

- [ ] **Step 4: 커밋**

```bash
git add keylens-env/tests/test_load_env_integration.py keylens-env/README.md
git commit -m "test(keylens-env): 실제 백엔드 end-to-end 통합 테스트 + README 완성

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>"
```

---

### Task 6: 프론트 — `sdkApi` 확장(프로젝트/디렉토리 CRUD) + 타입

**Files:**
- Modify: `frontend/src/api/types.ts` (파일 끝에 `SdkProject`/`SdkProjectDir` 추가)
- Modify: `frontend/src/api/client.ts` (`sdkApi` 확장)
- Modify: `frontend/src/types.ts` (`View`에 `'projectAccess'` 추가, `SdkProjectSummary`/`SdkDir` 프론트 타입 추가)

**Interfaces:**
- Consumes: `vreq<T>`(기존, `client.ts`)
- Produces (Task 7이 그대로 씀):
  - `SdkProject { project: string; key_count: number }` (API 계약)
  - `SdkProjectDir { id: number; path: string; source: 'manual' | 'approved'; created_at: string }` (API 계약)
  - `sdkApi.projects(): Promise<SdkProject[]>`
  - `sdkApi.dirs(project: string): Promise<SdkProjectDir[]>`
  - `sdkApi.addDir(project: string, path: string): Promise<SdkProjectDir>`
  - `sdkApi.removeDir(project: string, dirId: number): Promise<{ removed: boolean }>`
  - `View = 'input' | 'vault' | 'pending' | 'projectAccess'`
  - `SdkProjectSummary { project: string; keyCount: number }` (프론트 내부)
  - `SdkDir { id: number; path: string; source: 'manual' | 'approved'; createdAt: string }` (프론트 내부)

- [ ] **Step 1: `frontend/src/api/types.ts` 파일 끝에 추가**

```typescript
/** SDK 프로젝트 요약(RUNTIME-1) — 금고에 프로젝트가 지정된 항목이 있으면 자동으로 잡힌다. */
export interface SdkProject {
  project: string
  key_count: number
}

/** SDK 허용 디렉토리 한 건(RUNTIME-1). source: 'manual'(사전 등록) | 'approved'(승인 프롬프트로 등록). */
export interface SdkProjectDir {
  id: number
  path: string
  source: 'manual' | 'approved'
  created_at: string
}
```

- [ ] **Step 2: `frontend/src/api/client.ts` 수정**

import 블록의 타입 목록에 `SdkProject`/`SdkProjectDir` 추가(알파벳 순서 유지):

```typescript
import type {
  AnalyzeApiRequest,
  AnalyzeApiResponse,
  KnowledgeResponse,
  SdkPendingRequest,
  SdkProject,
  SdkProjectDir,
  VaultEntryCreate,
  VaultEntryMeta,
  VaultEntryUpdate,
  VaultHistoryEntry,
  VaultBundle,
  VaultImportResult,
  VaultStatus,
  VaultVerifyResult,
} from './types'
```

`sdkApi` 블록(파일 끝)을 통째로 바꾼다:

```typescript
// ── RUNTIME-1: SDK 접근 관리 — 승인 대기 + 프로젝트별 디렉토리 사전등록 ──

export const sdkApi = {
  pending: () => vreq<SdkPendingRequest[]>('/sdk/pending'),
  approve: (id: number) => vreq<{ approved: boolean }>(`/sdk/pending/${id}/approve`, { method: 'POST' }),
  deny: (id: number) => vreq<{ denied: boolean }>(`/sdk/pending/${id}/deny`, { method: 'POST' }),
  projects: () => vreq<SdkProject[]>('/sdk/projects'),
  dirs: (project: string) =>
    vreq<SdkProjectDir[]>(`/sdk/projects/${encodeURIComponent(project)}/directories`),
  addDir: (project: string, path: string) =>
    vreq<SdkProjectDir>(`/sdk/projects/${encodeURIComponent(project)}/directories`, {
      method: 'POST',
      body: JSON.stringify({ path }),
    }),
  removeDir: (project: string, dirId: number) =>
    vreq<{ removed: boolean }>(
      `/sdk/projects/${encodeURIComponent(project)}/directories/${dirId}`,
      { method: 'DELETE' },
    ),
}
```

- [ ] **Step 3: `frontend/src/types.ts` 수정**

`View` 타입(14번째 줄)을 바꾼다:

```typescript
/** 앱 셸 내부 뷰. */
export type View = 'input' | 'vault' | 'pending' | 'projectAccess'
```

파일 끝(`PendingRequest` 인터페이스 뒤)에 추가:

```typescript
/** SDK 프로젝트 요약(RUNTIME-1, 프론트 내부 표현). */
export interface SdkProjectSummary {
  project: string
  keyCount: number
}

/** SDK 허용 디렉토리 한 건(RUNTIME-1, 프론트 내부 표현). */
export interface SdkDir {
  id: number
  path: string
  source: 'manual' | 'approved'
  createdAt: string
}
```

- [ ] **Step 4: 타입체크**

Run: `cd frontend && npx tsc --noEmit`
Expected: 에러 0

- [ ] **Step 5: 커밋**

```bash
git add frontend/src/api/types.ts frontend/src/api/client.ts frontend/src/types.ts
git commit -m "feat(frontend): RUNTIME-1 sdkApi 확장 — 프로젝트/디렉토리 CRUD + 타입

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>"
```

---

### Task 7: 프론트 — 스토어(프로젝트 접근 상태·액션)

**Files:**
- Modify: `frontend/src/store/keylensStore.ts`

**Interfaces:**
- Consumes: `sdkApi`(Task 6), `SdkProjectSummary`/`SdkDir`(Task 6), `vaultErrorText`(기존, 같은 파일)
- Produces (Task 8이 그대로 씀):
  - `state.sdkProjects: SdkProjectSummary[]`
  - `state.selectedSdkProject: string | null`
  - `state.sdkDirs: SdkDir[]`
  - `state.newDirPath: string`
  - `goProjectAccess(): void`
  - `loadSdkProjects(): Promise<void>`
  - `selectSdkProject(project: string): void`
  - `setNewDirPath(v: string): void`
  - `addSdkDir(): Promise<void>`
  - `removeSdkDir(dirId: number): Promise<void>`

- [ ] **Step 1: import 수정**

`frontend/src/store/keylensStore.ts`의 타입 import 블록에 `SdkDir`/`SdkProjectSummary` 추가(알파벳 순서 유지):

```typescript
import type {
  AnalysisResult,
  DeleteTarget,
  DupTarget,
  InputMode,
  ManualRow,
  PendingRequest,
  Screen,
  SdkDir,
  SdkProjectSummary,
  UnknownItem,
  VaultItem,
  View,
} from '@/types'
```

- [ ] **Step 2: 인터페이스(`KeylensState`)에 상태·액션 시그니처 추가**

`pendingRequests: PendingRequest[]` 필드 바로 뒤에 추가:

```typescript
  // RUNTIME-1 — 프로젝트 접근 설정 화면
  /** 금고에 프로젝트가 지정된 항목이 있는 프로젝트 목록. */
  sdkProjects: SdkProjectSummary[]
  /** 설정 화면에서 선택된 프로젝트(없으면 null). */
  selectedSdkProject: string | null
  /** 선택된 프로젝트의 허용 디렉토리 목록. */
  sdkDirs: SdkDir[]
  /** 디렉토리 추가 입력 필드 값. */
  newDirPath: string
```

`denyPending: (id: number) => Promise<void>` 줄 바로 뒤에 액션 시그니처 추가:

```typescript
  /** 프로젝트 접근 설정 화면으로 전환하고 프로젝트 목록을 새로 불러온다. */
  goProjectAccess: () => void
  /** SDK 프로젝트 목록을 백엔드에서 다시 불러온다. */
  loadSdkProjects: () => Promise<void>
  /** 프로젝트를 선택하고 그 프로젝트의 허용 디렉토리 목록을 불러온다. */
  selectSdkProject: (project: string) => void
  /** 새 디렉토리 입력 필드 값 설정. */
  setNewDirPath: (v: string) => void
  /** 선택된 프로젝트에 디렉토리를 사전 등록(source=manual, 승인 팝업 없이 바로 통과). */
  addSdkDir: () => void
  /** 디렉토리 등록 해제. */
  removeSdkDir: (dirId: number) => void
```

- [ ] **Step 3: 초기 상태 값 추가**

`pendingRequests: [],` 줄 바로 뒤에 추가:

```typescript
    sdkProjects: [],
    selectedSdkProject: null,
    sdkDirs: [],
    newDirPath: '',
```

- [ ] **Step 4: 액션 구현 — `goPending: () => { ... }` 블록 바로 뒤에 추가**

```typescript
    goProjectAccess: () => {
      set({ view: 'projectAccess' })
      get().loadSdkProjects()
    },
```

- [ ] **Step 5: 액션 구현 — `denyPending` 블록 바로 뒤(`// ── 설정(최초 실행) ──` 주석 앞)에 추가**

```typescript
    loadSdkProjects: async () => {
      try {
        const rows = await sdkApi.projects()
        set({ sdkProjects: rows.map((p) => ({ project: p.project, keyCount: p.key_count })) })
      } catch {
        /* 목록 로딩 실패는 조용히 무시 */
      }
    },
    selectSdkProject: async (project) => {
      set({ selectedSdkProject: project, sdkDirs: [] })
      try {
        const rows = await sdkApi.dirs(project)
        set({
          sdkDirs: rows.map((d) => ({
            id: d.id,
            path: d.path,
            source: d.source,
            createdAt: d.created_at,
          })),
        })
      } catch (e) {
        get().showToast(vaultErrorText(e, '디렉토리 목록을 불러오지 못했어요'))
      }
    },
    setNewDirPath: (v) => set({ newDirPath: v }),
    addSdkDir: async () => {
      const project = get().selectedSdkProject
      const path = get().newDirPath.trim()
      if (!project) return
      if (!path) {
        get().showToast('등록할 디렉토리 경로를 입력해 주세요')
        return
      }
      try {
        await sdkApi.addDir(project, path)
        set({ newDirPath: '' })
        await get().selectSdkProject(project)
        get().showToast('디렉토리를 등록했어요 — 이후 자동으로 값을 받아갑니다')
      } catch (e) {
        get().showToast(vaultErrorText(e, '디렉토리 등록 실패 — 잠시 후 다시 시도해 보세요'))
      }
    },
    removeSdkDir: async (dirId) => {
      const project = get().selectedSdkProject
      if (!project) return
      try {
        await sdkApi.removeDir(project, dirId)
        await get().selectSdkProject(project)
        get().showToast('디렉토리 등록을 해제했어요')
      } catch (e) {
        get().showToast(vaultErrorText(e, '해제 실패 — 잠시 후 다시 시도해 보세요'))
      }
    },
```

- [ ] **Step 6: `resetProto()`에 리셋 추가**

`pendingRequests: [],` 줄(`resetProto` 안, 파일 끝 근방) 바로 뒤에 추가:

```typescript
        sdkProjects: [],
        selectedSdkProject: null,
        sdkDirs: [],
        newDirPath: '',
```

- [ ] **Step 7: 타입체크**

Run: `cd frontend && npx tsc --noEmit`
Expected: 에러 0

- [ ] **Step 8: 커밋**

```bash
git add frontend/src/store/keylensStore.ts
git commit -m "feat(frontend): RUNTIME-1 스토어 — 프로젝트 접근 설정 상태·액션

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>"
```

---

### Task 8: 프론트 — `ProjectAccessScreen` + Sidebar + App.tsx + BACKLOG 동기화

**Files:**
- Create: `frontend/src/components/screens/ProjectAccessScreen.tsx`
- Modify: `frontend/src/components/Sidebar.tsx`
- Modify: `frontend/src/App.tsx`
- Modify: `docs/BACKLOG.md`

**Interfaces:**
- Consumes: `useKeylens`(기존), `state.sdkProjects`/`selectedSdkProject`/`sdkDirs`/`newDirPath`/`loadSdkProjects`/`selectSdkProject`/`setNewDirPath`/`addSdkDir`/`removeSdkDir`/`goProjectAccess`(Task 7)
- Produces: 없음(이 플랜의 마지막 태스크)

- [ ] **Step 1: `frontend/src/components/screens/ProjectAccessScreen.tsx` 생성**

```typescript
// SPDX-FileCopyrightText: 2026 [Your Name]
// SPDX-License-Identifier: MIT
import { useEffect } from 'react'
import { useKeylens } from '@/store/keylensStore'

/** RUNTIME-1 — 프로젝트별 SDK 허용 디렉토리를 미리 등록해 두는 설정 화면.
 * 여기서 등록해 두면 keylens-env가 최초 요청에도 승인 팝업 없이 바로 통과한다. */
export function ProjectAccessScreen() {
  const sdkProjects = useKeylens((s) => s.sdkProjects)
  const selectedSdkProject = useKeylens((s) => s.selectedSdkProject)
  const sdkDirs = useKeylens((s) => s.sdkDirs)
  const newDirPath = useKeylens((s) => s.newDirPath)
  const loadSdkProjects = useKeylens((s) => s.loadSdkProjects)
  const selectSdkProject = useKeylens((s) => s.selectSdkProject)
  const setNewDirPath = useKeylens((s) => s.setNewDirPath)
  const addSdkDir = useKeylens((s) => s.addSdkDir)
  const removeSdkDir = useKeylens((s) => s.removeSdkDir)

  useEffect(() => {
    loadSdkProjects()
  }, [loadSdkProjects])

  return (
    <div className="mx-auto max-w-[720px] px-8 pb-[90px] pt-[44px] [animation:klFadeUp_.35s_ease]">
      <div className="mb-[18px]">
        <h1 className="m-0 text-[20px] font-bold tracking-[-.015em]">프로젝트 접근</h1>
        <div className="mt-1 text-[12.5px] text-faint-2">
          keylens-env SDK가 승인 팝업 없이 바로 통과할 디렉토리를 프로젝트별로 미리 등록해 두세요.
        </div>
      </div>

      {sdkProjects.length === 0 ? (
        <div className="rounded-xl border border-border bg-panel px-5 py-8 text-center text-[13px] text-muted">
          프로젝트가 지정된 키가 아직 없어요 — 보관함에서 항목에 프로젝트를 먼저 지정하세요.
        </div>
      ) : (
        <div className="flex gap-4">
          <div className="flex w-[220px] flex-none flex-col gap-1">
            {sdkProjects.map((p) => (
              <button
                key={p.project}
                type="button"
                onClick={() => selectSdkProject(p.project)}
                className={
                  'flex items-center justify-between rounded-lg border px-3 py-[9px] text-left text-[12.5px] font-semibold ' +
                  (p.project === selectedSdkProject
                    ? 'border-[rgba(62,207,142,.55)] bg-[#191F26] text-fg'
                    : 'border-border bg-surface text-muted hover:border-border-strong')
                }
              >
                <span className="truncate">{p.project}</span>
                <span className="text-[11px] text-faint-2">{p.keyCount}</span>
              </button>
            ))}
          </div>

          <div className="min-w-0 flex-1">
            {!selectedSdkProject ? (
              <div className="rounded-xl border border-border bg-panel px-5 py-8 text-center text-[13px] text-muted">
                왼쪽에서 프로젝트를 선택하세요.
              </div>
            ) : (
              <>
                <div className="mb-3 flex gap-2">
                  <input
                    value={newDirPath}
                    onChange={(e) => setNewDirPath(e.target.value)}
                    onKeyDown={(e) => {
                      if (e.key === 'Enter') addSdkDir()
                    }}
                    placeholder="예: C:\repo\블로그 또는 /home/user/repo/blog"
                    className="min-w-0 flex-1 rounded-lg border border-border bg-surface px-3 py-[9px] font-mono text-[12.5px] text-fg outline-none focus:border-[rgba(62,207,142,.55)]"
                  />
                  <button
                    type="button"
                    onClick={addSdkDir}
                    className="cursor-pointer rounded-lg border-none bg-mint px-4 py-[9px] text-[12.5px] font-bold text-on-mint hover:brightness-[1.07]"
                  >
                    등록
                  </button>
                </div>

                {sdkDirs.length === 0 ? (
                  <div className="rounded-xl border border-border bg-panel px-5 py-8 text-center text-[13px] text-muted">
                    등록된 디렉토리가 없어요.
                  </div>
                ) : (
                  <div className="flex flex-col gap-2">
                    {sdkDirs.map((d) => (
                      <div
                        key={d.id}
                        className="flex items-center gap-3 rounded-xl border border-border bg-panel px-4 py-[12px]"
                      >
                        <div className="min-w-0 flex-1">
                          <div className="truncate font-mono text-[12.5px] text-fg-soft">{d.path}</div>
                          <div className="mt-[3px] text-[10.5px] text-dim-3">
                            {d.source === 'manual' ? '사전 등록' : '승인으로 등록됨'} · {d.createdAt}
                          </div>
                        </div>
                        <button
                          type="button"
                          onClick={() => removeSdkDir(d.id)}
                          className="cursor-pointer rounded-lg border border-border bg-surface px-3 py-[9px] text-[12.5px] font-semibold text-muted hover:border-border-strong hover:text-fg-soft"
                        >
                          해제
                        </button>
                      </div>
                    ))}
                  </div>
                )}
              </>
            )}
          </div>
        </div>
      )}
    </div>
  )
}
```

- [ ] **Step 2: `frontend/src/components/Sidebar.tsx` 수정**

훅 선언부(`const goPending = useKeylens((s) => s.goPending)` 줄 바로 뒤)에 추가:

```typescript
  const goProjectAccess = useKeylens((s) => s.goProjectAccess)
```

`<nav>` 안, "승인 대기" 버튼(`</button>` 다음, `</nav>` 앞)에 새 버튼 추가:

```typescript
        <button type="button" onClick={goProjectAccess} className={navBtn(view === 'projectAccess')}>
          <span className="block size-[15px] flex-none rounded-[3px] border-[1.5px] border-current opacity-70" />
          <span className="flex-1">프로젝트 접근</span>
        </button>
```

- [ ] **Step 3: `frontend/src/App.tsx` 수정**

import 블록에 추가(`PendingScreen` import 바로 뒤):

```typescript
import { ProjectAccessScreen } from '@/components/screens/ProjectAccessScreen'
```

`<main>` 안의 뷰 분기에 한 줄 추가:

```typescript
          <main className="h-screen min-w-0 flex-1 overflow-y-auto">
            {view === 'input' && <InputScreen />}
            {view === 'vault' && <VaultScreen />}
            {view === 'pending' && <PendingScreen />}
            {view === 'projectAccess' && <ProjectAccessScreen />}
          </main>
```

- [ ] **Step 4: 타입체크 + 린트 + 빌드**

Run: `cd frontend && npx tsc --noEmit && npm run lint && npm run build`
Expected: 에러 0

- [ ] **Step 5: `docs/BACKLOG.md` 동기화**

아래는 전부 `docs/BACKLOG.md`의 `### RUNTIME-1` 섹션(현재 397~426번째 줄) 안의 편집이다. 각각
**이 문자열을 찾아서**(old) **이 문자열로 바꾼다**(new) — grep으로 찾으면 섹션 내에서 유일하게
매치된다.

**5-1. 섹션 헤더**

old:
```
### RUNTIME-1 ⚪ `keylens-env` — dotenv 대체 런타임 SDK (Python 우선, post-MVP)
```
new:
```
### RUNTIME-1 ✅ `keylens-env` — dotenv 대체 런타임 SDK (Python 우선) — 완료(데스크톱 채널)
```

**5-2. 진행 상황 문단**

old:
```
- **진행 상황(날짜는 이 파일을 수정하는 시점 기준):** 백엔드 기반(레포/서비스/모델/`/sdk/*` API) 구현 완료 — `docs/superpowers/plans/2026-07-30-runtime1-backend-foundation.md`, main에 병합 완료(커밋 `6341f3d`). 남은 3개 하위 플랜(프론트 설정 화면, `keylens-env` 패키지 자체, 데스크톱 알림) 중 **데스크톱 알림(Windows)**은 설계 확정 후 구현 완료 — `docs/superpowers/plans/2026-08-08-runtime1-desktop-notification.md`(작업표시줄 깜빡임 + OS 토스트 + `PendingScreen` 자동 화면전환, `VaultService.on_pending` 훅). 나머지 2개(프론트 설정 화면, `keylens-env` 패키지)는 아직 시작 전.
```
new:
```
- **진행 상황(2026-08-09 기준):** 4개 서브플랜(백엔드 기반, 데스크톱 알림, `keylens-env` 패키지, 프론트 프로젝트 접근 설정 화면) 전부 완료 — `docs/superpowers/plans/2026-07-30-runtime1-backend-foundation.md`(백엔드), `docs/superpowers/plans/2026-08-08-runtime1-desktop-notification.md`(데스크톱 알림), `docs/superpowers/plans/2026-08-09-keylens-env-package.md`(패키지+설정화면). 남은 건 브라우저 탭 알림 채널(개발 모드 전용 대체 수단, 스코프 하)과 실제 PyPI 업로드(계정 필요, 사용자 직접 진행)뿐이다.
```

**5-3. 프로젝트 식별 체크박스**

old:
```
  - [ ] **프로젝트 식별**: 소비 레포 루트에 설정 파일(`.keylens.toml`, `project = "블로그"`)을 둔다. `load_env()`가 `python-dotenv`의 `.env` 탐색과 같은 방식으로 cwd에서 위로 탐색해 찾는다.
```
new:
```
  - [x] **프로젝트 식별**: 소비 레포 루트에 설정 파일(`.keylens.toml`, `project = "블로그"`)을 둔다. `load_env()`가 `python-dotenv`의 `.env` 탐색과 같은 방식으로 cwd에서 위로 탐색해 찾는다.
```

**5-4. 보안 프레이밍 체크박스**

old:
```
  - [ ] **보안 프레이밍(문서화 필수)**: 이 기능이 새 신뢰 경계를 만드는 게 아니라는 점을 README/위협모델에 명시한다 — 잠금 해제 상태에선 이미 로컬 프로세스가 vault API를 호출할 수 있었다(기존 위협모델 그대로). 이 기능이 실제로 추가하는 가치는 "전부 다 보임" 대신 **승인된 프로젝트 것만** 내려주는 최소 권한 스코핑이다.
```
new:
```
  - [x] **보안 프레이밍(문서화 필수)**: 이 기능이 새 신뢰 경계를 만드는 게 아니라는 점을 README/위협모델에 명시한다 — 잠금 해제 상태에선 이미 로컬 프로세스가 vault API를 호출할 수 있었다(기존 위협모델 그대로). 이 기능이 실제로 추가하는 가치는 "전부 다 보임" 대신 **승인된 프로젝트 것만** 내려주는 최소 권한 스코핑이다.
```

**5-5. 신규 의존성 체크박스**

old:
```
  - [ ] **신규 의존성**: PyPI 배포용 패키징(예: `hatchling`/`setuptools`, 둘 다 MIT/permissive) · 데스크톱 알림용 `plyer`(MIT) — 착수 시 license-check.
```
new:
```
  - [x] **신규 의존성**: `keylens-env` 빌드 백엔드로 `setuptools`(PSF/BSD, 카피레프트 전이 의존성 없음 — hatchling은 전이 의존성 pathspec이 MPL-2.0이라 기각) · 데스크톱 알림용 `plyer`(MIT, 이미 완료).
```

**5-6. 테스트 체크리스트 5개**

old:
```
  - [ ] 🧪 KeyLens 미실행/잠금 상태에서 `load_env()` → 명확한 에러(조용한 실패 없음)
  - [ ] 🧪 미등록 디렉토리 최초 요청 → 승인 팝업 → 허용 후 값 주입, 거부 시 접근 안 됨
  - [ ] 🧪 기본(전역) 키 + 프로젝트 키 이름 충돌 → 프로젝트 쪽이 우선, 비충돌 시 합집합
  - [ ] 🧪 등록 안 된 다른 프로젝트 디렉토리에서는 해당 프로젝트 전용 키에 접근 불가
  - [ ] 🧪 SDK 경유 조회가 감사 이력에 기록됨
```
new:
```
  - [x] 🧪 KeyLens 미실행/잠금 상태에서 `load_env()` → 명확한 에러(조용한 실패 없음) — `keylens-env/tests/test_load_env_integration.py`
  - [x] 🧪 미등록 디렉토리 최초 요청 → 승인 팝업 → 허용 후 값 주입, 거부 시 접근 안 됨 — `backend/tests/test_sdk_session.py`(백엔드 기반 플랜에서 이미 커버)
  - [x] 🧪 기본(전역) 키 + 프로젝트 키 이름 충돌 → 프로젝트 쪽이 우선, 비충돌 시 합집합 — `backend/tests/test_sdk_repo.py::test_entries_for_env_project_overrides_global_on_name_conflict`
  - [x] 🧪 등록 안 된 다른 프로젝트 디렉토리에서는 해당 프로젝트 전용 키에 접근 불가 — `backend/tests/test_sdk_repo.py::test_entries_for_env_other_project_not_included`
  - [x] 🧪 SDK 경유 조회가 감사 이력에 기록됨 — `backend/tests/test_sdk_session.py::test_sdk_env_logs_audit_history`
```

(아래 2개 브라우저 알림 관련 항목은 이번 플랜 범위 밖이므로 그대로 `[ ]`로 둔다 — 수정하지 않는다.)

**5-7. 착수 시점 줄**

old:
```
- **착수 시점**: 사용자가 직접 지정.
```
new:
```
- **완료(2026-08-09)**: 데스크톱 채널 기준 RUNTIME-1 전체 완료. 남은 건 브라우저 탭 알림 채널과 실제 PyPI 업로드뿐(둘 다 스코프 밖 또는 사용자 직접 진행).
```

- [ ] **Step 6: 수동 브라우저 확인**

Run: `node scripts/dev.mjs`(루트에서) → `http://localhost:5173` → 로그인 → 보관함에서 항목 하나에
프로젝트 이름 지정(예: "블로그") → 사이드바 "프로젝트 접근" 클릭 → 왼쪽에 "블로그" 프로젝트가 뜨는지
확인 → 선택 후 디렉토리 경로 입력해 "등록" → 목록에 나타나는지, "해제"로 지워지는지 확인.

- [ ] **Step 7: 커밋**

```bash
git add frontend/src/components/screens/ProjectAccessScreen.tsx frontend/src/components/Sidebar.tsx frontend/src/App.tsx docs/BACKLOG.md
git commit -m "feat(frontend): RUNTIME-1 ProjectAccessScreen — 프로젝트별 디렉토리 사전등록 + BACKLOG 동기화

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>"
```

---

## 수동 검증 (이 플랜의 자동화 범위 밖)

1. `pip install -e keylens-env/`가 신선한 venv에서도 깨끗이 되는지(README 안내대로) 확인.
2. 실제 데스크톱 exe(`python desktop/app.py` 또는 빌드된 exe)를 켜 놓고, 별도 터미널에서 `.keylens.toml`을
   둔 임의 디렉토리에서 `python -c "import keylens_env; keylens_env.load_env(); import os; print(os.environ['...'])"`
   실행 → 승인 대기 알림(작업표시줄·토스트) 확인 → "프로젝트 접근" 화면에서 사전 등록해 두면
   재실행 시 승인 팝업 없이 바로 값을 받아오는지 확인.
3. 실제 PyPI 업로드는 사용자가 계정·API 토큰 준비 후 별도 진행(`python -m build && twine upload dist/*`).

## Self-Review 메모 (계획 작성자 확인용)

- **스펙 커버리지**: 설계 스펙의 "구성 요소" 표 12행 — `pyproject.toml`/`README.md`/`__init__.py`/
  `exceptions.py`(Task 1) · `config.py`(Task 2) · `client.py`(Task 3, `__init__.py` 재수정은 Task 4) ·
  통합테스트(Task 5) · `frontend/src/api/client.ts`·`types.ts`·`api/types.ts`(Task 6) ·
  `keylensStore.ts`(Task 7) · `ProjectAccessScreen.tsx`·`Sidebar.tsx`·`App.tsx`(Task 8) — 전부 태스크로
  매핑됨. "즉시 실패(fail-fast)" 핵심 설계 판단은 `load_env()`가 폴링 없이 예외를 그대로 전파하는 것으로
  충족(Task 4). "path=.keylens.toml 위치, 명시 project는 cwd" 규칙은 Task 4의 `load_env()` 본문과
  Task 5의 통합 테스트 양쪽에서 검증됨.
- **플레이스홀더 스캔**: 없음 — 모든 스텝에 완전한 코드·정확한 명령·기대 출력 포함.
- **타입 일관성**: `find_config() -> tuple[str, Path]`가 Task 2(정의)·Task 4(`load_env()`에서 구조
  분해 `resolved_project, config_dir = find_config()`) 동일. `fetch_env(project, path, base_url) -> dict[str, str]`가
  Task 3(정의)·Task 4(호출) 동일 시그니처. `SdkProjectDir{id, path, source, created_at}` →
  `SdkDir{id, path, source, createdAt}` 필드 매핑이 Task 6(타입 정의)·Task 7(`selectSdkProject`의
  매핑 코드) 동일하게 맞음.
- **빌드 백엔드 재확인**: license-auditor 조사 결과(hatchling의 전이 의존성 pathspec=MPL-2.0)를 반영해
  전 태스크에서 `setuptools`만 쓴다 — Task 1의 `pyproject.toml`에 hatchling 언급 없음.
