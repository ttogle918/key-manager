<!--
SPDX-FileCopyrightText: 2026 [Your Name]
SPDX-License-Identifier: MIT
-->

# 지식베이스 스키마 (`knowledge/*.yaml`)

각 YAML 파일은 서비스 하나를 선언한다. 파일 하나를 추가하면 코드 수정 없이 분류 대상에 포함된다 (SPEC 4.4).

```yaml
service: notion               # 고유 식별자 (소문자 slug)
display_name: Notion          # 표시명
credentials:                  # 이 서비스가 발급하는 자격증명 종류들
  - kind: api_key             # 종류 식별자 (서비스 내 고유)
    label: "API Key"          # 프론트 표시 라벨
    label_patterns:           # Stage2 라벨 신호 — OCR 주변 텍스트와 대조 (부분일치, 대소문자 무시)
      - "Internal Integration Token"
      - "API key"
    url_patterns:             # Stage2 URL 신호 — 정규식(그룹 1이 값 위치)
      - "notion\\.so/[^/]+/([0-9a-fA-F]{32})\\?v="
    value_regex: "^(secret_|ntn_)[A-Za-z0-9]{36,}$"  # Stage1 값 기반 — 접두사가 명확할 때만. 애매하면 null
    official_env_name: NOTION_API_KEY                # 표준 환경변수명 (SPEC 4.5)
    expiry_known: false       # 만료가 값에서 파싱 가능한가 (JWT 등)
```

## 필드 규칙

- **value_regex**: 값만으로 종류를 단정할 수 있을 때만 채운다. UUID·고정길이 hex처럼 여러 종류가 형식을 공유하면 `null`로 두고 `label_patterns`/`url_patterns`(Stage2)에 의존한다 — 이것이 KeyLens의 차별점(맥락 기반 분류)이다.
- **정규식 출처**: 각 서비스 공식 문서의 키 포맷을 보고 직접 작성한다. ⚠️ TruffleHog(AGPL) 코드/패턴을 포팅하지 않는다 (CLAUDE.md). MIT인 Gitleaks 패턴을 참고했다면 `THIRD-PARTY-NOTICES.md`에 출처를 남긴다.
- **anchoring**: `value_regex`는 토큰 전체 일치를 전제로 `^…$` 앵커를 포함한다.
