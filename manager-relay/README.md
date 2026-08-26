<!--
SPDX-FileCopyrightText: 2026 ttogle918
SPDX-License-Identifier: MIT
-->
# KeyLens 매니저 릴레이

계정·DB 없이 **SMTP로만** KeyLens 금고 번들을 이메일로 전달하는 독립 배포형 서비스입니다.
이 코드는 레포에 있지만 **실행 서버가 아닙니다** — 이 기능을 쓰고 싶은 사람("매니저")이
자기 SMTP 자격증명으로 직접 배포해야 동작합니다. 설계 배경은
[`docs/superpowers/specs/2026-08-26-sync2-email-relay-design.md`](../docs/superpowers/specs/2026-08-26-sync2-email-relay-design.md)를 참고하세요.

## 로컬 실행

```bash
cd manager-relay
python -m venv .venv && . .venv/Scripts/activate  # Windows(Git Bash). macOS/Linux는 source .venv/bin/activate
pip install -r requirements-dev.txt
cp .env.example .env  # 값 채우기 — Gmail이면 앱 비밀번호 필요(2단계 인증 계정)
set -a && source .env && set +a
python -m app.main  # http://localhost:8090
```

## 배포(예: GCloud Cloud Run)

`SMTP_HOST`/`SMTP_PORT`/`SMTP_USER`/`SMTP_PASS`/`PUBLIC_BASE_URL`을 배포 환경변수로 설정하세요.
**`min-instances=1`을 권장**합니다 — 이 서비스는 확인 대기 중인 요청을 프로세스 메모리에만
들고 있어서(TTL 15분), 스케일-투-제로로 인스턴스가 재활용되면 그 사이의 요청이 유실될 수
있습니다(사용자가 다시 요청하면 됩니다 — 설계 문서의 판단 3 참고).

## 프론트엔드 연결

배포한 주소를 KeyLens 프론트의 `VITE_SYNC_RELAY_URL`에 설정하면 "이메일로 내보내기" 버튼이
나타납니다(미설정 시 자동으로 숨겨짐 — `frontend/.env.example` 참고).
