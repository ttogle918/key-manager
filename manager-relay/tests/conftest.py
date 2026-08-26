# SPDX-FileCopyrightText: 2026 ttogle918
# SPDX-License-Identifier: MIT
"""app.main import 시점의 fail-fast(SMTP env 필수) 를 테스트에서도 만족시키는 더미 값."""
import os

os.environ.setdefault("SMTP_HOST", "smtp.test.invalid")
os.environ.setdefault("SMTP_PORT", "587")
os.environ.setdefault("SMTP_USER", "relay@test.invalid")
os.environ.setdefault("SMTP_PASS", "test-password")
os.environ.setdefault("PUBLIC_BASE_URL", "http://localhost:8080")
