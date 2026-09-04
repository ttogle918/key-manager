# SPDX-FileCopyrightText: 2026 [Your Name]
# SPDX-License-Identifier: MIT
"""SMTP 발송 — 표준 라이브러리 smtplib만 쓴다(새 런타임 의존성 0).

Gmail 앱 비밀번호부터 Resend/SendGrid의 SMTP 엔드포인트까지 env 값만 바꾸면 그대로
교체된다(docs/superpowers/specs/2026-08-26-sync2-email-relay-design.md 판단 1).
"""
from __future__ import annotations

import os
import smtplib
from email.message import EmailMessage


class MailSendError(Exception):
    """SMTP 발송 실패(네트워크·인증 오류)를 이 예외 하나로 정규화한다."""


class SmtpConfig:
    def __init__(self, host: str, port: int, user: str, password: str, use_tls: bool = True) -> None:
        self.host = host
        self.port = port
        self.user = user
        self.password = password
        self.use_tls = use_tls

    @classmethod
    def from_env(cls, env: dict[str, str] | None = None) -> "SmtpConfig":
        e = env if env is not None else os.environ
        missing = [k for k in ("SMTP_HOST", "SMTP_USER", "SMTP_PASS") if not e.get(k)]
        if missing:
            raise RuntimeError(f"SMTP 설정이 없습니다 - 환경변수 {', '.join(missing)} 를 설정하세요")
        return cls(
            host=e["SMTP_HOST"],
            port=int(e.get("SMTP_PORT", "587")),
            user=e["SMTP_USER"],
            password=e["SMTP_PASS"],
            use_tls=e.get("SMTP_USE_TLS", "true").lower() != "false",
        )


def send_confirm_email(config: SmtpConfig, destination_email: str, confirm_url: str) -> None:
    msg = EmailMessage()
    msg["Subject"] = "[KeyLens] 금고 내보내기 요청 확인"
    msg["From"] = config.user
    msg["To"] = destination_email
    msg.set_content(
        "KeyLens에서 이 주소로 금고 내보내기 요청이 있었습니다.\n\n"
        f"본인이 요청한 것이 맞다면 아래 링크를 클릭해 실제 파일을 받으세요:\n{confirm_url}\n\n"
        "요청한 적이 없다면 이 메일을 무시하세요 - 클릭하지 않으면 아무 일도 일어나지 않습니다.\n"
        "이 링크는 15분간만 유효합니다."
    )
    _send(config, msg)


def send_bundle_email(config: SmtpConfig, destination_email: str, bundle_json: str) -> None:
    msg = EmailMessage()
    msg["Subject"] = "[KeyLens] 암호화된 금고 백업 파일"
    msg["From"] = config.user
    msg["To"] = destination_email
    msg.set_content(
        "요청하신 KeyLens 금고 백업 파일을 첨부했습니다.\n\n"
        "비밀 값은 암호화되어 있어 원래 금고의 마스터 비밀번호가 있어야만 열 수 있습니다.\n"
        "다만 서비스명·라벨·프로젝트명·메모 같은 메타데이터는 평문으로 포함되어 있어,\n"
        "이 메일을 중계한 매니저와 그의 메일 제공자가 볼 수 있습니다.\n"
        "다른 기기의 KeyLens에서 '가져오기'로 이 첨부파일을 지정해 복원하세요."
    )
    msg.add_attachment(
        bundle_json.encode("utf-8"),
        maintype="application",
        subtype="json",
        filename="keylens-vault.klvault.json",
    )
    _send(config, msg)


def _send(config: SmtpConfig, msg: EmailMessage) -> None:
    try:
        with smtplib.SMTP(config.host, config.port, timeout=10) as smtp:
            if config.use_tls:
                smtp.starttls()
            smtp.login(config.user, config.password)
            smtp.send_message(msg)
    except (smtplib.SMTPException, OSError) as e:
        raise MailSendError(f"메일 발송 실패: {e}") from e
