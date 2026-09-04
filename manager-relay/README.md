<!--
SPDX-FileCopyrightText: 2026 [Your Name]
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
리스닝 포트는 `PORT` 환경변수를 우선 사용합니다(Cloud Run 등 대부분의 PaaS가 이 변수를
주입합니다 — 미설정 시 `8090`으로 폴백). 저장소에 포함된 `Dockerfile`로 바로 빌드·배포할 수
있습니다:

```bash
cd manager-relay
docker build -t keylens-manager-relay .
docker run -p 8090:8090 --env-file .env keylens-manager-relay
```

**`--max-instances=1`은 권장이 아니라 필수**입니다 — 이 서비스의 토큰 저장소는 인스턴스
프로세스 메모리에만 있고 여러 인스턴스가 공유하지 않습니다. 인스턴스가 2개 이상으로
늘어나면(강의실 동시 접속 등 부하 상황에서 정확히 벌어지는 일입니다) `POST /sync/request`와
그 뒤의 `/sync/confirm`이 서로 다른 인스턴스로 라우팅될 수 있고, 이 경우 멀쩡한 요청도
"토큰 없음"(410)으로 실패합니다. `min-instances=1`도 함께 설정하는 것을 권장합니다 —
스케일-투-제로로 인스턴스가 재활용되면 그 사이 대기 중이던 요청이 유실될 수 있기 때문입니다
(사용자가 다시 요청하면 됩니다 — 설계 문서의 판단 3 참고). 두 설정은 서로 다른 문제를 막으므로
`max-instances=1`만으로는 충분하지 않고 함께 설정해야 합니다.

## 발송 흐름 (3단계)

1. `POST /sync/request` - 목적지 주소로 **확인 링크만** 담긴 메일을 보내고, **6자리 확인 코드**를
   요청한 앱에 응답으로 돌려줍니다. **코드는 메일에 넣지 않습니다.**
2. `GET /sync/confirm?token=...` - 코드 입력 폼만 보여줍니다. **부작용이 없습니다.**
3. `POST /sync/confirm` - 코드가 맞아야 번들을 발송합니다. 5회 틀리면 요청을 버립니다.

2단계가 발송을 하지 않는 게 중요합니다. Gmail·Outlook ATP 같은 메일 보안 스캐너는 메일 속
링크를 사용자 대신 미리 열어봅니다. 예전처럼 `GET`이 곧바로 발송하면, 사용자가 누르지도
않았는데 번들이 나가고 정작 사용자가 누를 때는 "만료됐다"는 화면을 보게 됩니다. 폼 제출을
거치게 하면 프리페치로는 발송이 일어나지 않습니다.

코드를 메일이 아니라 앱 화면에만 띄우는 이유는 따로 있습니다. **수신 주소를 오타 냈을 때**
확인 메일은 그 낯선 사람에게 갑니다. 링크 하나가 곧 발송 권한이면 그 사람이 번들을 받아갈 수
있지만, 코드는 요청을 시작한 사람의 화면에만 있으므로 발송을 끝낼 수 없습니다.

## 매니저가 볼 수 있는 것

비밀 값은 암호화되어 있어 매니저도, 그의 메일 제공자도 열어볼 수 없습니다. 다만 번들에는
`service`(서비스명)·`label`(라벨)·`project`(프로젝트명)·`memo`(메모) 같은 **메타데이터가
평문으로 포함**되어 있어, 이 릴레이를 운영하는 매니저와 그의 메일 제공자(예: Google)는 "이
사용자가 어떤 서비스의 자격증명을 갖고 있는지"를 볼 수 있습니다.

또한 `smtp.gmail.com` 등 대부분의 SMTP 제공자는 발송 계정의 "보낸 편지함"에 매 발송분의
사본을 **영구적으로** 남깁니다 — 릴레이 프로세스 자신은 요청 처리가 끝나면 메모리에서 아무것도
남기지 않지만, 매니저의 메일 계정에는 모든 릴레이 이력(메타데이터 포함)이 계속 쌓입니다. 이
노출을 줄이고 싶다면 보낸 편지함을 주기적으로 비우거나, 보낸 편지함 개념이 없는 트랜잭션
메일 API로 교체하는 것은 운영자(매니저) 본인의 책임입니다.

## 프론트엔드 연결

배포한 주소를 KeyLens 프론트의 `VITE_SYNC_RELAY_URL`에 설정하면 "이메일로 내보내기" 버튼이
나타납니다(미설정 시 자동으로 숨겨짐 — 저장소 루트의 `.env.example` 참고).
