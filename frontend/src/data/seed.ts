// SPDX-FileCopyrightText: 2026 [Your Name]
// SPDX-License-Identifier: MIT
import type { AnalysisResult, VaultItem } from '@/types'

/**
 * 프로토타입 시연용 초기 보관함 데이터.
 * ⚠️ 전부 명백한 더미 값 (CLAUDE.md 시크릿 위생 규칙). 실제 키 없음.
 * 실제 앱에선 암호화된 로컬 저장소에서 로드된다.
 */
export function seedVault(): VaultItem[] {
  return [
    { id: 'n1', service: 'Notion', type: 'API Key', varName: 'NOTION_API_KEY', masked: 'secret_ntn_••••••••••••i9j0', full: 'secret_ntn_a1b2c3d4e5f6g7h8i9j0', addedAt: '2026-05-28', project: '블로그 자동화', context: '워크스페이스 "사이드프로젝트"', memo: '개인 블로그 자동 발행용 내부 통합', sourceImage: 'sample', expiresAt: null, history: [{ date: '2026-05-28', event: '등록' }], meta: { source: 'screenshot', label: 'Internal Integration Token', workspace: '사이드프로젝트', detected_by: 'secret_ prefix' } },
    { id: 'n2', service: 'Notion', type: 'Database ID', varName: 'NOTION_DATABASE_ID', masked: '3f9a1c2e-••••-••••-••••-2d5e8a7b4c3f', full: '3f9a1c2e-7b4d-4e8a-9c1f-2d5e8a7b4c3f', addedAt: '2026-05-28', project: '블로그 자동화', context: '"제품 로드맵" 데이터베이스', memo: '로드맵 DB 연동', sourceImage: 'sample', expiresAt: null, history: [{ date: '2026-05-28', event: '등록' }], meta: { source: 'url', ocr_title: '제품 로드맵', url_hint: 'notion.so/team/…?v=', detected_by: 'segment before ?v=' } },
    { id: 'n3', service: 'Notion', type: 'Page ID', varName: 'NOTION_PAGE_ID', masked: 'a1b2c3d4-••••-••••-••••-0e1f2a3b4c5d', full: 'a1b2c3d4-e5f6-4a7b-8c9d-0e1f2a3b4c5d', addedAt: '2026-06-03', project: '블로그 자동화', context: '"주간 회의록" 페이지', memo: '회의록 자동 아카이브', sourceImage: null, expiresAt: null, history: [{ date: '2026-06-03', event: '등록' }], meta: { source: 'url', ocr_title: '주간 회의록', detected_by: 'last path segment' } },
    { id: 'k1', service: 'Kakao', type: 'REST API 키', varName: 'KAKAO_REST_API_KEY', masked: '4f8e2a1b••••••••••••••••3a7b', full: '4f8e2a1b9c3d7e6f5a4b8c2d1e9f3a7b', addedAt: '2026-04-15', project: '로그인 서비스', context: '앱 "사이드프로젝트-로그인"', memo: '카카오 소셜 로그인 도입', sourceImage: 'sample', expiresAt: null, history: [{ date: '2026-04-15', event: '등록' }], meta: { source: 'screenshot', console_tab: 'REST API 키', app_name: '사이드프로젝트-로그인' } },
    { id: 'k2', service: 'Kakao', type: 'JavaScript 키', varName: 'KAKAO_JS_KEY', masked: '9c3d7e6f••••••••••••••••2b8a', full: '9c3d7e6f5a4b8c2d1e9f3a7b4c6d2b8a', addedAt: '2026-04-15', project: '로그인 서비스', context: '앱 "사이드프로젝트-로그인"', memo: '웹 SDK 지도 표시용', sourceImage: 'sample', expiresAt: null, history: [{ date: '2026-04-15', event: '등록' }], meta: { source: 'screenshot', console_tab: 'JavaScript 키', app_name: '사이드프로젝트-로그인' } },
    { id: 'k3', service: 'Kakao', type: 'Admin 키', varName: 'KAKAO_ADMIN_KEY', masked: '1e9f3a7b••••••••••••••••7c4d', full: '1e9f3a7b4c6d2b8a9e5f3a1b6d8e7c4d', addedAt: '2026-04-15', project: '로그인 서비스', context: '앱 "사이드프로젝트-로그인"', memo: '서버 푸시 발송 — 회전 예정', sourceImage: null, expiresAt: '2026-07-09', history: [{ date: '2026-04-15', event: '등록' }, { date: '2026-06-01', event: '키 회전' }], meta: { source: 'screenshot', console_tab: 'Admin 키', rotate_due: '2026-07-09' } },
    { id: 'g1', service: 'GCP', type: 'API Key', varName: 'GOOGLE_API_KEY', masked: 'AIzaSyFA••••••••••••kJ6h', full: 'AIzaSyFAKE9xY2zW8vU3tR1qP0oN7mL5kJ6h', addedAt: '2026-03-02', project: '개인 블로그', context: '프로젝트 "my-blog-1234"', memo: 'Maps 지오코딩용 — 사용량 제한 걸어둠', sourceImage: null, expiresAt: '2026-07-05', history: [{ date: '2026-03-02', event: '등록' }], meta: { source: 'text', gcp_project: 'my-blog-1234', restriction: 'HTTP referrer' } },
    { id: 'g2', service: 'GCP', type: 'API Key', varName: 'GOOGLE_API_KEY', masked: 'AIzaSyZZ••••••••••••q2W9', full: 'AIzaSyZZfAkE1aB2cD3eF4gH5iJ6kL7q2W9', addedAt: '2026-06-25', project: '지도 데모', context: '프로젝트 "map-demo-5678"', memo: '행사 부스 지도 데모용', sourceImage: null, expiresAt: '2026-08-30', history: [{ date: '2026-06-25', event: '등록' }], meta: { source: 'text', gcp_project: 'map-demo-5678' } },
    { id: 'o1', service: 'OpenAI', type: 'API Key', varName: 'OPENAI_API_KEY', masked: 'sk-proj-aAbB••••••••••hIi4', full: 'sk-proj-aAbBcC1dDeE2fFgG3hIi4', addedAt: '2026-06-20', project: '요약 실험', context: '개인 조직', memo: '요약 기능 실험용', sourceImage: 'sample', expiresAt: null, history: [{ date: '2026-06-20', event: '등록' }], meta: { source: 'screenshot', org: 'personal', detected_by: 'sk- prefix' } },
  ]
}

/**
 * "분석" 버튼을 눌렀을 때 나오는 목업 결과 세트.
 * 실제 앱에선 백엔드 분류 엔진(SPEC 4.2/4.3)이 반환한다.
 */
export function freshResults(): AnalysisResult[] {
  return [
    { id: 'r1', service: 'Notion', typeKey: 'api_key', conf: 'high', masked: 'secret_ntn_••••••••••••i9j0', full: 'secret_ntn_a1b2c3d4e5f6g7h8i9j0', format: 'secret_ 접두어', source: '스크린샷 · .env 미리보기 3행', context: '라벨 "Internal Integration Token" 감지 — 워크스페이스 "사이드프로젝트"', memo: '', project: '', metaOpen: false, meta: { source: 'screenshot', label: 'Internal Integration Token', workspace: '사이드프로젝트', detected_by: 'secret_ prefix', line: 3 } },
    { id: 'r2', service: 'Notion', typeKey: 'database_id', conf: 'high', masked: '3f9a1c2e-••••-••••-••••-2d5e8a7b4c3f', full: '3f9a1c2e-7b4d-4e8a-9c1f-2d5e8a7b4c3f', format: 'UUID v4', source: '스크린샷 · notion.so URL의 ?v= 앞 세그먼트', context: '페이지 제목 "제품 로드맵" — 이 UUID는 그 데이터베이스를 가리킵니다', memo: '', project: '', metaOpen: false, meta: { source: 'url', ocr_title: '제품 로드맵', url_hint: 'notion.so/team/…?v=', detected_by: 'segment before ?v=' } },
    {
      id: 'r3', service: 'Notion', typeKey: '', conflict: true, conf: 'low', masked: '8c2d4f6a-••••-••••-••••-9f0a1b2c3d4e', full: '8c2d4f6a-1e3b-4a5c-8d7e-9f0a1b2c3d4e', format: 'UUID v4', source: '스크린샷 · 설정 패널 캡처', memo: '', project: '', metaOpen: false, meta: { source: 'screenshot', nearby_label: 'Data sources', url_position: 'last path segment', conflict: true },
      options: [
        { k: 'data_source_id', label: 'Data Source ID', varName: 'NOTION_DATA_SOURCE_ID', evidence: "값 바로 위에 'Data sources' 라벨이 보임 — 텍스트 신호", signal: '신호 강함', strong: true },
        { k: 'page_id', label: 'Page ID', varName: 'NOTION_PAGE_ID', evidence: 'notion.so/… URL의 마지막 세그먼트 위치 — 위치 신호', signal: '신호 약함', strong: false },
      ],
    },
    { id: 'r4', service: 'OpenAI', typeKey: 'api_key', conf: 'high', masked: 'sk-proj-aAbB••••••••••hIi4', full: 'sk-proj-aAbBcC1dDeE2fFgG3hIi4', format: 'sk- 접두어', source: '스크린샷 · 터미널 출력', context: 'export OPENAI_API_KEY=… 라인에서 발견', memo: '', project: '', metaOpen: false, meta: { source: 'screenshot', shell_line: 'export OPENAI_API_KEY=…', detected_by: 'sk- prefix' } },
    { id: 'r5', service: 'Kakao', typeKey: 'rest_api_key', conf: 'mid', masked: '4f8e2a1b••••••••••••••••3a7b', full: '4f8e2a1b9c3d7e6f5a4b8c2d1e9f3a7b', format: '32자리 hex', source: '스크린샷 · Kakao Developers 콘솔', context: '앱 이름 "사이드프로젝트-로그인" 헤더 감지', midNote: 'REST·Admin 키는 형식이 같아요 — 콘솔 탭 이름 "REST API 키"로 추정했습니다.', memo: '', project: '', metaOpen: false, meta: { source: 'screenshot', console_tab: 'REST API 키', app_name: '사이드프로젝트-로그인' } },
  ]
}
