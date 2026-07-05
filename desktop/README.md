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

## 배포용 실행 파일(.exe/.app)로 패키징 — 선택

`python desktop/app.py`로도 충분히 쓰지만, **비개발자에게 더블클릭 설치**를 주려면 단일 실행 파일로 묶습니다.
그 결과물을 [GitHub Releases](https://github.com/ttogle918/key-manager/releases)에 올리고 랜딩·블로그에서 링크하면 됩니다.

> ⚠️ **패키저 라이선스 주의(이 프로젝트는 permissive-only)**
> - 가장 흔한 **PyInstaller는 GPL-2.0**(빌드 도구). 생성물엔 예외 조항이 있으나, 본 프로젝트 규칙상
>   카피레프트 도구 도입은 **먼저 결정**이 필요하다(`CLAUDE.md`). 그래서 기본 채택하지 않았다.
> - **permissive 대안**: `cx_Freeze`(PSF/permissive) 또는 `Nuitka`(Apache-2.0). 이 중 하나로 패키징 권장.
> - 패키징 시 데이터 파일로 `frontend/dist/`, `backend/knowledge/*.yaml` 을 **함께 포함**해야 한다.

패키징은 실행 파일이 커서(수십 MB) 저장소에 커밋하지 않고 Releases 아티팩트로만 배포한다.
구체 스텝은 패키저 선택 후 이 문서에 추가한다(현재는 소스 실행까지 제공).

## 라이선스

- `pywebview` — BSD-3-Clause (permissive). Windows 전이 의존성 `pythonnet`/`clr-loader` = MIT.
- WebView2 런타임은 Windows 11 기본 포함 OS 구성요소(파이썬 의존성 아님).
- 전부 카피레프트 없음. 상세는 루트 [THIRD-PARTY-NOTICES.md](../THIRD-PARTY-NOTICES.md)·[docs/SBOM.md](../docs/SBOM.md).
