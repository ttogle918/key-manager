<!--
SPDX-FileCopyrightText: 2026 [Your Name]
SPDX-License-Identifier: MIT
-->

# 화면 설명 — Tavily 검색 + 로컬 발견 캐시 설계 (판단 5·6 구체화)

> `docs/superpowers/specs/2026-08-27-screenshot-explain-design.md`(1단계 설계, 이미 구현됨)의 판단
> 5·6을 실제로 구현 가능한 수준까지 구체화한다. 원본 문서는 아키텍처를 정했지만 캐시 매칭
> 알고리즘·Tavily 도메인 제한 범위는 구체적으로 안 적혀 있었고, 브레인스토밍 중 원본 문서 판단 6에
> **자기모순**을 하나 발견해 정정했다(아래 판단 A).

## 이미 구현된 것 (1단계, 변경 없음)

`backend/app/ocr.py`의 `run_ocr_lines()`(줄 단위 박스 보존), `backend/app/explain.py`의 지식베이스
대조(`known` 등급) + 로컬 Ollama 1차 추론(`ai_unverified` 등급), `ExplainModal.tsx` 오버레이. 이번
작업은 `ai_unverified`로 끝나던 미분류 줄에 **Tavily 검색으로 확인된 `ai_verified` 등급**과
**로컬 발견 캐시 재사용**을 추가한다.

## 판단 A(원본 문서 판단 6 정정) — Tavily 검색은 도메인 제한 없이

**원본 문서의 모순**: "검색은 지식베이스에 전혀 없는 서비스를 만났을 때만 의미가 있다"고 해놓고,
바로 그 검색을 "지식베이스의 기존 `docs_url` 도메인으로 제한"하라고 되어 있었다 — 새 서비스는
정의상 지식베이스에 없으므로, 이미 아는 도메인으로 제한하면 새 서비스의 공식 문서를 애초에 못
찾는다.

**정정**: `include_domains` 제한을 두지 않는다. 대신 검색 쿼리 자체에 `"{추측한 서비스명} 공식
문서"`처럼 품질 유도 키워드를 넣고, 검색 결과를 다시 LLM에 주어 "이 결과가 실제로 그 서비스의
공식 문서가 맞는지" 판단하게 한다 — 도메인 화이트리스트가 아니라 **LLM 재검증**이 신뢰 경계다.
지식베이스 도메인은 여전히 "이미 아는 서비스는 검색 자체를 생략"하는 데만 쓰인다(1단계 로직
그대로).

## 판단 B — 두 단계 로컬 Ollama 호출(추측 → 검증)

기존 1단계 프롬프트(`_PROMPT_TEMPLATE`)는 "이 줄이 뭔지 15자 이내로 설명"만 물었다. Tavily 검색을
걸려면 **검색할 서비스명**이 먼저 필요하므로, 1차 프롬프트를 확장해 `guessed_service`(서비스/제품명
추측, 모르면 `null`)도 같이 받는다.

- **1차 추론**(기존 확장): 미분류 줄들 → `{index, label, guessed_service}` 배열. `guessed_service`가
  있고 `TAVILY_API_KEY`가 설정돼 있으면 다음 단계로.
- **검색**: `tavily_client.search(f"{guessed_service} 공식 문서")`, 도메인 제한 없음, 상위 3건.
- **2차 추론(검증)**: 원본 줄 텍스트 + 추측한 서비스명 + 검색 결과(제목·URL·스니펫)를 LLM에 다시
  주고, "검색 결과가 그 서비스의 공식 문서·홈페이지가 맞으면 최종 라벨 + 문서 URL을, 아니면(관련
  없거나 불확실하면) '알 수 없음'을" 요청. 확인되면 `ai_verified` + `docs_url`, 아니면 1차 추론의
  `label`로 `ai_unverified`(기존 동작 그대로).
- Tavily 미설정이거나 `guessed_service`가 없으면 검색 단계 자체를 건너뛰고 곧바로 `ai_unverified` —
  기존 1단계 동작과 동일.

## 판단 C — 캐시 매칭: OCR 라인 정규화 비교

브레인스토밍 결정: `local_discoveries.yaml` 재사용 판단은 **OCR 라인 텍스트를 정규화한 뒤 정확히
일치하는지**로 한다(임베딩 유사도 같은 새 의존성·계산 로직 없이 최대한 단순하게).

- **정규화**: 값처럼 보이는 토큰(영숫자·`-`·`_` 6자 이상 연속)을 `<VALUE>`로 치환 + 공백 정규화.
  라벨 문구는 그대로 남고 값만 지워지므로, 같은 UI를 다시 만났을 때(값은 달라도 라벨은 동일)
  매칭된다.
- **저장/조회 둘 다 백엔드가 계산**한다(프론트는 원본 `text`만 보낸다) — 정규화 로직이 한 곳에만
  있어야 저장 시점과 조회 시점의 계산이 어긋나지 않는다.
- 캐시 히트 시: 저장된 `{label, tier, docs_url}`을 그대로 써서 Ollama·Tavily를 아예 건너뛴다(원본
  설계 "재사용" 요구사항 그대로).

## 판단 D — 승인 API는 원본 설계보다 필드를 줄인다

원본 문서는 `POST /explain/discoveries {pattern, guessed_service, guessed_docs_url}`이라고
적었지만, `guessed_service`는 캐시 재사용 로직(판단 C) 자체엔 필요 없고 사람이 나중에 지식베이스로
승격할 때 참고하는 주석 수준의 정보라 이번 범위에서는 뺀다(YAGNI — 필요해지면 나중에 추가). 실제
바디는 프론트가 이미 갖고 있는 `ExplainBox`의 필드 그대로:

```
POST /explain/discoveries {text, label, tier, docs_url}
```

`text`(OCR 원본 줄)를 백엔드가 판단 C의 정규화를 거쳐 `pattern`으로 변환해 저장한다. `tier`가
`known`이면 애초에 저장 대상이 아니므로 422로 거부.

## 나머지는 원본 설계 그대로

- 저장 위치: `backend/local_discoveries.yaml`(`.gitignore` 대상, `KEYLENS_LOCAL_DISCOVERIES_PATH`로
  경로 재정의 가능).
- `confirmed: false` 고정 — 이 프로젝트 안에서는 절대 `true`로 안 바뀜. 승격은 사람이 지식베이스
  YAML에 직접 반영해야만.
- 저장 시점은 자동 아님 — 사용자가 화면에서 항목별로 "저장" 눌러야만.
- Tavily는 완전 옵트인(`TAVILY_API_KEY` 없으면 검색 단계 자체가 없음, 기능 전체가 죽지 않음 —
  Ollama와 달리 "없으면 버튼이 안 보임"이 아니라 "없으면 그 등급만 낮아짐").
- 새 런타임 의존성 0 — Tavily 호출도 `ollama_client.py`와 동일하게 표준 라이브러리 `urllib`만 사용.

## 범위 밖 (이번에도 안 함)

로컬 발견 캐시의 지식베이스 자동 승격, 여러 캐시 항목 간 유사도 랭킹(정확 일치만), Tavily 외
검색 provider(SerpAPI 등) 지원 — 필요해지면 별도 provider 추상화가 있어야 하므로 이번 범위 밖으로
명시적으로 뺌.
