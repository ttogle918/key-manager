<!--
SPDX-FileCopyrightText: 2026 [Your Name]
SPDX-License-Identifier: MIT
-->
# 기여 가이드 (Contributing)

KeyLens에 기여해 주셔서 감사합니다. 이 프로젝트는 **MIT 라이선스**이며, 가장 흔한 기여는
**새 서비스 지식베이스 추가**입니다 — 코드 수정 없이 YAML 한 개면 됩니다.

## 빠른 시작

```bash
git clone https://github.com/ttogle918/key-manager.git
cd key-manager
# 설치·실행은 README.md 참고
```

브랜치를 따서 작업하고, 아래 체크리스트를 통과시킨 뒤 Pull Request를 보내주세요.

## 가장 쉬운 기여 — 새 서비스 추가 (YAML 하나)

`backend/knowledge/<service>.yaml` 파일 하나만 추가하면 **백엔드 분류와 프론트 UI 양쪽에 자동 반영**됩니다
(프론트는 부팅 시 `/knowledge`를 읽어 종류맵·서비스 목록을 동적 구성 — 프론트 코드 수정 불필요).

```yaml
# SPDX-FileCopyrightText: 2026 [Your Name]
# SPDX-License-Identifier: MIT
service: example                 # 소문자 id(고유)
display_name: Example            # 화면 표시명
credentials:
  - kind: api_key                # 종류 id
    label: "API Key"             # 표시 라벨
    label_patterns:              # OCR/텍스트 라벨 사전(한글·영문, 대소문자 무시)
      - "Secret key"
      - "시크릿 키"
    url_patterns: []             # 콘솔/리소스 URL에서 종류를 판별할 정규식(있으면)
    value_regex: "^ex_[A-Za-z0-9]{24,}$"   # 접두어가 명확할 때만. 없으면 null(라벨 맥락으로만 분류)
    official_env_name: EXAMPLE_API_KEY
    expiry_known: false
    # (선택) 키 유효성 검증용 read-only 엔드포인트 — TRUST-1
    # verify:
    #   method: GET
    #   url: "https://api.example.com/v1/me"
    #   auth: bearer             # bearer | header(+header_name,prefix) | query(+query_name)
    #   extra_headers: {}        # 예: {"User-Agent": "KeyLens"}
```

### 정규식(value_regex) 작성 규칙 ⚠️

- **각 서비스의 공식 문서를 근거로 직접 작성**하세요(접두어·길이·문자셋).
- **TruffleHog의 코드/탐지 패턴을 포팅하지 마세요** — AGPL-3.0이라 MIT와 충돌합니다.
- MIT인 Gitleaks 패턴을 참고했다면 `THIRD-PARTY-NOTICES.md`에 출처를 남기세요.
- 접두어가 없어 값만으로 단정할 수 없는 종류(예: AWS Secret, 32자 UUID)는 `value_regex: null`로 두고
  `label_patterns`/`url_patterns`(Stage2 맥락)로만 식별합니다 — **오탐(잘못된 단정)을 만들지 마세요.**

### 테스트 추가

`backend/tests/`에 값 매칭 + 오탐 방지 케이스를 추가하세요(예: `test_new_services.py` 참고).

```python
def test_example(kb):
    items = classify_text("ex_" + "A" * 24, kb)   # 더미 값만!
    assert items[0].service == "example"
    assert items[0].official_env_name == "EXAMPLE_API_KEY"
```

## 커밋·PR 체크리스트

- [ ] **새 파일 맨 위에 SPDX 헤더 2줄** (저작권 표기 + MIT 라이선스 식별자)
- [ ] **허용적(permissive) 라이선스 의존성만** 추가 (MIT/Apache-2.0/BSD/ISC). **카피레프트(GPL/AGPL/LGPL/MPL) 금지** — 필요하면 이슈로 먼저 문의
- [ ] **실제 키·시크릿 없음** — 예시·테스트는 명백한 더미(`sk-xxxxxxxx`)만
- [ ] 백엔드: `cd backend && ./.venv/Scripts/python.exe -m pytest -q` (또는 `python -m pytest -q`) 통과
- [ ] 프론트: `cd frontend && npm run build` (타입체크+번들) 통과
- [ ] `reuse lint` 통과(SPDX 헤더 누락 0), `pip-licenses`/`license-checker`에 카피레프트 0
- [ ] README의 지원 서비스 목록/문서를 코드와 일치하게 갱신

## 커밋 메시지

[Conventional Commits](https://www.conventionalcommits.org/)를 따릅니다: `feat(knowledge): …`, `fix(frontend): …`, `docs: …`.

## 버그·제안

GitHub Issues로 알려주세요. 보안 취약점은 공개 이슈 대신 저장소 소유자에게 비공개로 알려주시면 감사하겠습니다.
