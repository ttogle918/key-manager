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
pip install "git+https://github.com/ttogle918/key-manager.git@v0.1.1#subdirectory=keylens-env"
```

`requirements.txt`에 넣을 때도 같은 줄을 그대로 쓰면 됩니다.

이 레포를 직접 클론해 개발 중이라면 편집 가능 설치:

```bash
pip install -e keylens-env/
```

> PyPI 배포는 나중에 추가할 수 있습니다. 그때도 위 git 설치 방식은 계속 동작합니다.

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
