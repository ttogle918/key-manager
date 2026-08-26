# SPDX-FileCopyrightText: 2026 [Your Name]
# SPDX-License-Identifier: MIT
"""SMTP 발송 — smtplib.SMTP를 monkeypatch해 실제 네트워크 없이 호출 인자만 검증한다."""
import smtplib

import pytest

from app.mailer import MailSendError, SmtpConfig, send_bundle_email, send_confirm_email

CONFIG = SmtpConfig(host="smtp.example.com", port=587, user="relay@example.com", password="pw")


class FakeSmtp:
    sent_messages = []

    def __init__(self, host, port, timeout=10):
        self.host = host
        self.port = port

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def starttls(self):
        pass

    def login(self, user, password):
        self.user = user
        self.password = password

    def send_message(self, msg):
        FakeSmtp.sent_messages.append(msg)


@pytest.fixture(autouse=True)
def _reset_fake_smtp(monkeypatch):
    FakeSmtp.sent_messages = []
    monkeypatch.setattr(smtplib, "SMTP", FakeSmtp)


def test_smtp_config_from_env_reads_required_fields():
    config = SmtpConfig.from_env(
        {"SMTP_HOST": "h", "SMTP_PORT": "2525", "SMTP_USER": "u", "SMTP_PASS": "p"}
    )
    assert config.host == "h" and config.port == 2525 and config.user == "u"


def test_smtp_config_from_env_missing_required_raises():
    with pytest.raises(RuntimeError):
        SmtpConfig.from_env({})


def test_send_confirm_email_delivers_link():
    send_confirm_email(CONFIG, "dest@example.com", "https://relay.example.com/sync/confirm?token=abc")
    assert len(FakeSmtp.sent_messages) == 1
    msg = FakeSmtp.sent_messages[0]
    assert msg["To"] == "dest@example.com"
    assert "https://relay.example.com/sync/confirm?token=abc" in msg.get_content()


def test_send_bundle_email_attaches_json():
    send_bundle_email(CONFIG, "dest@example.com", '{"format": "klvault"}')
    assert len(FakeSmtp.sent_messages) == 1
    msg = FakeSmtp.sent_messages[0]
    assert msg["To"] == "dest@example.com"
    attachments = list(msg.iter_attachments())
    assert len(attachments) == 1
    assert attachments[0].get_content().decode("utf-8") == '{"format": "klvault"}'
    assert attachments[0].get_filename() == "keylens-vault.klvault.json"


def test_send_error_normalizes_to_mail_send_error(monkeypatch):
    class BrokenSmtp(FakeSmtp):
        def login(self, user, password):
            raise smtplib.SMTPAuthenticationError(535, b"bad credentials")

    monkeypatch.setattr(smtplib, "SMTP", BrokenSmtp)
    with pytest.raises(MailSendError):
        send_confirm_email(CONFIG, "dest@example.com", "https://relay.example.com/sync/confirm?token=abc")
