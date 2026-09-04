<!--
SPDX-FileCopyrightText: 2026 [Your Name]
SPDX-License-Identifier: MIT
-->
# KeyLens 데스크톱 앱

로컬 웹앱을 **네이티브 창 하나**로 감싼 실행기입니다. 브라우저·터미널 없이 KeyLens를 띄웁니다.
여전히 **100% 로컬** — 외부 서버 없음, 데이터는 이 기기의 `backend/vault.db`(암호문)에만 있습니다.

## 어떻게 동작하나

1. FastAPI 백엔드에 **빌드된 프론트(`frontend/dist`)를 정적 서빙**으로 얹어, API와 화면을 **같은 오리진**에서 제공(포트 무관, CORS 불필요).
2. `uvicorn`을 `127.0.0.1` 로컬에만 바인딩해 백그라운드 스레드로 기동.
3. OS 내장 웹뷰(Windows=WebView2 · macOS=WebKit · Linux=GTK/Qt)로 창을 열어 로드.
4. 창을 닫으면 서버도 함께 종료.

## 실행 (개발자)

```bash
# 1) 프론트 빌드(한 번) — dist 생성
cd frontend && npm ci && npm run build && cd ..

# 2) 데스크톱 의존성 설치 (백엔드 venv 재사용 권장)
cd backend && python -m venv .venv && .venv\Scripts\activate   # 이미 있으면 activate만
pip install -r ../desktop/requirements.txt && cd ..

# 3) 실행
python desktop/app.py
```

네이티브 창이 뜨고, 최초 실행 시 마스터 비밀번호로 금고를 생성합니다.

## 배포용 실행 파일(.exe/.app)로 패키징

`python desktop/app.py`로도 충분하지만, **비개발자에게 더블클릭 설치**를 주려면 단일 실행 파일로 묶습니다.
패키저는 **cx_Freeze**(permissive 라이선스, 아래 참고)를 사용합니다.

> ⚠️ **반드시 가상환경(venv) 안에서 빌드하세요.** 아래 2단계의 `activate` 를 빼먹고 전역 Python에
> 설치하면 빌드가 이렇게 실패합니다:
>
> ```
> RecursionError: maximum recursion depth exceeded
> ```
>
> cx_Freeze 가 import 그래프를 **재귀로** 훑는데, 패키지가 많이 깔린 전역 Python에서는 파이썬 기본
> 재귀 한도(1000)를 넘겨 버리기 때문입니다(실측: 전역 347개 패키지 → 실패 / venv 190개 → 성공).
> cx_Freeze 버전 문제가 아니므로 버전을 올리거나 내려도 해결되지 않습니다.

```bash
# 1) 프론트 빌드(실행 파일에 동봉될 SPA)
cd frontend && npm ci && npm run build && cd ..

# 2) 데스크톱 + 패키저 설치 — venv 활성화 필수(위 경고 참고)
cd backend && .venv\Scripts\activate && cd ..
pip install -r desktop/requirements-build.txt

# 3) 빌드 (2단계에서 활성화한 venv 그대로)
cd desktop && python setup.py build
#   → desktop/build/exe.<플랫폼>/KeyLens(.exe) + 옆에 frontend/dist·backend/knowledge 동봉

# 4) 배포용 zip 만들기 (위생 검사 포함)
cd desktop && python package.py
#   → desktop/build/KeyLens-v<버전>-win64.zip
```

### 배포 zip 은 반드시 `package.py` 로 만드세요

`build/exe.*` 를 직접 압축하면 안 됩니다. **패키징된 앱은 금고를 실행 파일 옆에 만들기 때문에**,
빌드한 exe 를 한 번 실행해 보는 것만으로(= 정상적인 스모크 테스트) 산출물 안에 `vault.db` 가
생기고 그대로 딸려 들어갑니다. v0.5.0 배포본에 실제로 빈 `vault.db` 가 들어갔습니다.

`package.py` 는 압축 전에 금고·SQLite 저널·`.env` 를 걷어내고, 완성된 zip 을 다시 열어
재확인합니다. 내용이 들어 있거나 열리지 않는 금고를 만나면 **지우지 않고 멈춥니다** - 자동
삭제는 그 자체가 데이터 사고이고, 앱이 실행 중이라 잠긴 금고일 수도 있기 때문입니다.
이 가드는 CI(`packaging-guard-test`)에서 매번 테스트합니다.

`requirements-build.txt` 는 런타임 의존성(`requirements.txt`)에 패키저(`cx_Freeze==8.6.4`)만 얹은
빌드 전용 목록입니다 — cx_Freeze 는 실행 파일에 실리지 않는 도구라 런타임 목록과 분리해 뒀습니다.

`setup.py` 가 실행 파일 옆에 `frontend/dist`·`backend/knowledge` 를 동봉하고, `app.py` 는 **패키징 모드
(`sys.frozen`)를 감지**해 그 경로에서 SPA·지식베이스를 읽습니다. 금고(`vault.db`)는 실행 파일 옆에 생성됩니다.

빌드 산출물(`build/`·`dist/`)은 용량이 커(수십 MB) 저장소에 커밋하지 않고
[GitHub Releases](https://github.com/ttogle918/key-manager/releases) 아티팩트로만 배포합니다.

> ✅ **빌드 실증**: cx_Freeze 8.6.4 + `backend/.venv` 에서 `KeyLens.exe` 생성 확인. 실행 시 번들된
> 지식베이스(10종)·SPA를 로드하고 백엔드가 정상 서빙됨(`/health`·`/knowledge`·`/analyze` 응답,
> 더미 GitHub 키 분류까지 확인).
>
> 2026-08-30 재빌드 확인 — 동봉물: `frontend/dist`, `backend/knowledge` YAML 9종,
> OCR 모델 `.onnx` 9개, 번들 총 392MB.

### 패키저 라이선스 (이 프로젝트는 permissive-only)

| 패키저 | 라이선스 | 채택 |
|---|---|---|
| **cx_Freeze** | **PSF 계열 permissive**(카피레프트 없음, 상용·독점 사용 허용) | ✅ **기본** |
| PyInstaller | GPL-2.0 **+ 예외 조항** — 생성 실행 파일은 자유 라이선스(MIT) 가능, 부트로더 미수정 시 GPL 전파 없음 | 대안(예외 조항 확인 후 사용 가능) |
| Nuitka | Apache-2.0 (permissive) | 대안 |

- cx_Freeze·PyInstaller·Nuitka **모두 빌드 도구**라 배포물(실행 파일)에 **도구 코드가 실리지 않는다.**
  cx_Freeze 는 애초에 permissive라 가장 깔끔하고, PyInstaller 는 예외 조항 덕에 생성물이 GPL에 묶이지 않는다.
- 자세한 라이선스 근거: [PyInstaller 라이선스 FAQ](https://pyinstaller.org/en/stable/license.html) ·
  [cx_Freeze 라이선스](https://cx-freeze.readthedocs.io/en/latest/license.html).

## 라이선스

- `pywebview` 6.2.1 — BSD-3-Clause (permissive). 전이 `pythonnet`·`clr-loader`·`bottle`·`proxy_tools` = MIT.
- `plyer` 2.1.0 — MIT (permissive). 전이 의존성 없음. OS 네이티브 토스트 알림(RUNTIME-1).
- WebView2 런타임은 Windows 11 기본 포함 OS 구성요소(파이썬 의존성 아님).
- 전부 카피레프트 없음. 상세는 루트 [THIRD-PARTY-NOTICES.md](../THIRD-PARTY-NOTICES.md)·[docs/SBOM.md](../docs/SBOM.md).
