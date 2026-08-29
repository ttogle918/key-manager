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

## 설치

**PyPI에 올리지 않습니다.** git 저장소에서 바로 설치하세요 — 이 패키지는 레포 안의
`keylens-env/` 서브디렉토리에 있습니다.

```bash
# 다른 프로젝트에서 쓰기 (권장)
pip install "git+https://github.com/ttogle918/key-manager.git#subdirectory=keylens-env"

# 특정 버전(태그)으로 고정하고 싶다면
pip install "git+https://github.com/ttogle918/key-manager.git@v0.3.0#subdirectory=keylens-env"
```

`requirements.txt`에 넣을 때도 같은 줄을 그대로 쓰면 됩니다.

이 레포를 직접 클론해 개발 중이라면 편집 가능 설치:

```bash
pip install -e keylens-env/
```

> **패키지 버전은 KeyLens 앱 릴리스 태그와 별개입니다.** 이 패키지의 버전은 SDK 자체가 바뀔 때만
> 올라가므로, 앱이 `v0.2.0`이어도 `keylens_env.__version__`은 `0.1.0`일 수 있습니다.
> 그래서 `pip install --upgrade`는 패키지 버전이 그대로면 갱신을 건너뜁니다 — 최신 커밋으로 다시
> 받으려면 `--force-reinstall`을 쓰거나 위처럼 태그를 명시해 고정하세요.

> PyPI 배포는 나중에 추가할 수 있습니다. 그때도 위 git 설치 방식은 계속 동작합니다.

## 사용법

1. 소비 프로젝트 루트에 `.keylens.toml`을 만듭니다:

```toml
collection = "블로그"
```

> 예전 문서대로 `project = "블로그"` 라고 써 둔 파일도 계속 그대로 동작합니다
> (백엔드 API 필드명과 DB 컬럼은 아직 `project`라서 옛 이름을 계속 받습니다).

2. 코드에서:

```python
import keylens_env

keylens_env.load_env()  # os.environ에 주입, 실패 시 예외

import os
print(os.environ["OPENAI_API_KEY"])
```

`.keylens.toml` 없이 컬렉션을 직접 지정할 수도 있습니다:

```python
keylens_env.load_env("블로그")
```

> 직접 지정하면 **스크립트를 실행하는 디렉토리마다 따로 승인**이 필요합니다
> (승인 단위가 "현재 작업 디렉토리"라서 하위 폴더에서 실행하면 새 요청이 생깁니다).
> `.keylens.toml` 방식은 파일이 있는 위치가 항상 승인 단위라 한 번만 승인하면 됩니다.

이미 셸이나 CI에 설정해 둔 환경변수를 살리고 싶으면 `override=False`
(python-dotenv의 기본 동작과 같습니다):

```python
keylens_env.load_env(override=False)  # 기존 os.environ 값이 이깁니다
```

## 컬렉션 목록 보기

무엇을 쓸 수 있는지 확인할 때 씁니다. **값은 나오지 않고 이름과 개수만** 나오며,
금고가 잠겨 있어도 조회됩니다.

터미널에서:

```bash
keylens-env collections          # 또는: python -m keylens_env collections
```

```text
컬렉션        키 개수
----------  -------
블로그            3
2026-08-29        1
```

코드에서:

```python
import keylens_env

for c in keylens_env.collections():
    print(c.name, c.key_count)     # Collection(name=..., key_count=...)
```

어디에 어떻게 붙는지 진단하려면:

```bash
keylens-env where
```

> **`2026-08-29`처럼 날짜 이름이 보인다면**, KeyLens에서 **컬렉션을 지정하지 않고**
> 저장한 키들이 등록일로 묶인 것입니다. 이 키들은 `load_env("블로그")`로는 오지 않습니다 —
> KeyLens 앱에서 해당 항목의 컬렉션을 원하는 이름으로 바꿔 주세요.

## 접근 승인

`.keylens.toml`이 있는 디렉토리가 KeyLens에 **처음 요청**하면, KeyLens 앱에 승인 대기 알림이
뜹니다(KeyLens의 "컬렉션 접근" 화면에서 미리 등록해 둘 수도 있습니다 — 그러면 승인 팝업
없이 바로 통과합니다). 승인하기 전까지는 `KeylensApprovalPendingError`가 발생합니다 —
`load_env()`는 승인을 기다리지 않고 즉시 실패합니다. 승인 후 스크립트를 다시 실행하세요.

승인과 디렉토리 등록은 **금고가 잠금 해제된 상태에서만** 가능합니다(권한을 주는 행위라서).
반대로 등록 해제·거부는 잠긴 상태에서도 됩니다.

## 자동 잠금 주의

KeyLens 금고는 **무활동 5분이면 자동으로 잠깁니다**. 그리고 SDK 조회는 이 타이머를
갱신하지 않습니다 — 자리를 비운 사용자를 보호하기 위한 설계입니다. 즉 앱 화면을 만지지
않으면, 스크립트를 계속 돌리고 있어도 5분 뒤부터 `KeylensLockedError`가 납니다.

길게 돌리는 작업이라면 KeyLens를 띄울 때 시간을 늘리세요:

```bash
# Windows
set KEYLENS_AUTOLOCK_SECONDS=3600
# macOS/Linux
export KEYLENS_AUTOLOCK_SECONDS=3600
```

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
except keylens_env.KeylensEmptyCollectionError:
    print("컬렉션이 비었어요 — keylens-env collections 로 목록을 확인하세요")
except keylens_env.KeylensConfigError as e:
    print(f".keylens.toml 설정 문제: {e}")
```

또는 한 번에:

```python
except keylens_env.KeylensEnvError as e:
    print(f"KeyLens 연동 실패: {e}")
```

이 패키지는 **어떤 실패에서도 `KeylensEnvError` 밖의 예외를 내보내지 않습니다** — 응답이
깨졌거나 그 포트에 다른 프로그램이 떠 있어도 마찬가지입니다. 그리고 성공했는데 주입할
변수가 0개인 경우도 조용히 넘어가지 않고 `KeylensEmptyCollectionError`로 알려 줍니다.

## 접속 주소

기본값은 **자동 탐색**입니다 — 데스크톱 exe 포트(`127.0.0.1:8765`)와 개발 모드 포트
(`127.0.0.1:8003`)를 순서대로 확인해서 **실제로 KeyLens가 응답하는 쪽**에 붙습니다.
그래서 exe로 쓰든 `node scripts/dev.mjs`로 쓰든 별도 설정이 필요 없습니다.

다른 포트로 띄웠다면 명시할 수 있습니다(이 값이 있으면 자동 탐색은 하지 않습니다):

```bash
export KEYLENS_BASE_URL=http://127.0.0.1:9000   # Windows: set KEYLENS_BASE_URL=...
```

## 보안 프레이밍

이 SDK가 새로운 신뢰 경계를 만드는 건 아닙니다 — 잠금 해제 상태에선 이미 로컬 프로세스가
KeyLens vault API를 호출할 수 있었습니다(기존 위협모델 그대로). 이 SDK가 실제로 추가하는
가치는 "전부 다 보임" 대신 **승인된 컬렉션 것만** 내려주는 최소 권한 스코핑입니다.
스코핑을 대상이 스스로 부여할 수 없도록, 디렉토리 등록·승인은 금고가 잠금 해제된
상태에서만 가능합니다(등록 해제·거부는 잠긴 상태에서도 됩니다).

## 개발자용 — 테스트 실행

```bash
cd backend && .venv/Scripts/python.exe -m pytest ../keylens-env/tests -v
```

`test_load_env_integration.py`만 backend 의존성(fastapi·uvicorn)이 필요합니다 — 그 외
테스트는 keylens-env 자체 외에 아무것도 필요 없습니다.

## 라이선스

MIT — [../LICENSE](../LICENSE) 참고.
