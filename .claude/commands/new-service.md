---
description: 지식베이스(knowledge/*.yaml)에 새 서비스 정의 추가 — 스키마 준수 + 테스트 동반
argument-hint: [서비스명, 예: stripe]
---

# 새 서비스 지식베이스 추가: $ARGUMENTS

지식베이스는 이 프로젝트의 확장성 핵심이자 오픈소스 기여 유도 포인트다. 코드 수정 0으로 YAML 한 개 추가만으로 분류 대상에 포함되어야 한다.

## 절차

1. **공식 문서 조사**: $ARGUMENTS 서비스의 개발자 콘솔에서 발급되는 자격증명 종류를 조사하라.
   - 각 자격증명의 **콘솔 화면 라벨** (한글/영문 모두 — OCR 매칭용)
   - 값 형식 (접두사, 길이, 문자셋) — 있으면 `value_regex`로
   - 관련 **URL 패턴** (콘솔 URL, 리소스 URL에서 ID가 노출되는 위치)
   - 커뮤니티/공식 문서에서 통용되는 **표준 환경변수명**
   - ⚠️ 키 포맷은 **각 서비스의 공식 문서 기준으로 직접 작성**하라. TruffleHog 패턴 참조 금지(AGPL). Gitleaks(MIT) 참고 시 THIRD-PARTY-NOTICES.md에 출처 기록.

2. **YAML 작성**: `knowledge/$ARGUMENTS.yaml`
```yaml
service: <service_id>
display_name: <표시명>
credentials:
  - kind: <종류 id, 예: api_key>
    label_patterns:            # OCR 라벨 사전 (대소문자 무시 매칭 전제)
      - "Secret key"
      - "시크릿 키"
    url_patterns: []           # 예: "dashboard.example.com/apikeys"
    value_regex: null          # 접두사가 명확할 때만, 예: "^sk_live_[A-Za-z0-9]{24,}$"
    official_env_name: <ENV_NAME>
    expiry_known: false
```

3. **더미 값 규칙**: 예시·테스트에 넣는 값은 반드시 명백한 가짜만 사용 (`sk_live_xxxxxxxxxxxx` 등). 실제 발급 키 절대 금지.

4. **테스트 추가**: `tests/knowledge/test_$ARGUMENTS.py`
   - 스키마 검증 통과
   - 라벨 매칭 케이스 (한글/영문 각 1개 이상)
   - value_regex가 있으면 더미 키 매칭 + 무작위 문자열 비매칭(오식별 금지)
   - 동일 형식 값이 여러 종류 존재하는 서비스면(노션 UUID류) 맥락 구분 케이스 필수

5. **검증 실행**: 로더 스키마 검증 + `pytest tests/knowledge/ -q` 통과 확인. 중복 `official_env_name` 경고가 없는지 확인.

6. **문서 갱신**: README의 지원 서비스 목록에 추가.

새 파일에는 SPDX 헤더를 잊지 마라 (YAML은 `# SPDX-...` 주석).
