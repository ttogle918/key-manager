# SPDX-FileCopyrightText: 2026 [Your Name]
# SPDX-License-Identifier: MIT
"""collections() 공개 API + `python -m keylens_env` CLI.

컬렉션 목록은 "무엇을 쓸 수 있는지" 확인용이라 값은 절대 다루지 않는다 - 이름과 개수만.
"""
import keylens_env
from keylens_env import __main__ as cli


def test_collections_returns_named_tuples(monkeypatch):
    monkeypatch.setattr(
        keylens_env,
        "fetch_collections",
        lambda: [{"project": "블로그", "key_count": 3}, {"project": "사이드", "key_count": 1}],
    )
    rows = keylens_env.collections()

    assert rows == [("블로그", 3), ("사이드", 1)]
    assert rows[0].name == "블로그"
    assert rows[0].key_count == 3


def test_collections_empty(monkeypatch):
    monkeypatch.setattr(keylens_env, "fetch_collections", lambda: [])
    assert keylens_env.collections() == []


def test_cli_collections_prints_names_and_counts(monkeypatch, capsys):
    monkeypatch.setattr(
        keylens_env,
        "fetch_collections",
        lambda: [{"project": "블로그", "key_count": 3}, {"project": "2026-08-29", "key_count": 1}],
    )
    assert cli.main(["collections"]) == 0

    out = capsys.readouterr().out
    assert "블로그" in out and "3" in out
    assert "2026-08-29" in out


def test_cli_collections_empty_is_not_an_error(monkeypatch, capsys):
    monkeypatch.setattr(keylens_env, "fetch_collections", lambda: [])
    assert cli.main(["collections"]) == 0
    assert "없어요" in capsys.readouterr().out


def test_cli_reports_error_without_traceback(monkeypatch, capsys):
    """CLI는 traceback을 쏟지 않고 한 줄 메시지 + 종료 코드 1로 끝나야 한다."""

    def boom():
        raise keylens_env.KeylensNotRunningError("KeyLens를 찾을 수 없어요")

    monkeypatch.setattr(keylens_env, "fetch_collections", boom)

    assert cli.main(["collections"]) == 1
    assert "KeylensNotRunningError" in capsys.readouterr().out


def test_cli_unknown_command(capsys):
    assert cli.main(["nope"]) == 2
    assert "알 수 없는 명령" in capsys.readouterr().out


class _Cp949Stdout:
    """encoding='cp949'인 콘솔 흉내 - 실제 콘솔처럼 인코딩 불가 문자에서 죽는다."""

    encoding = "cp949"

    def __init__(self):
        self.written = []

    def write(self, text):
        text.encode("cp949")  # 여기서 UnicodeEncodeError가 나면 테스트 실패
        self.written.append(text)


def test_cli_output_survives_cp949_console(monkeypatch):
    """한글 콘솔(cp949)에서 인코딩 불가 문자가 섞여도 CLI가 죽지 않아야 한다."""
    bad_name = "ሴ—A"  # cp949에 없는 문자를 일부러 섞는다
    monkeypatch.setattr(
        keylens_env, "fetch_collections", lambda: [{"project": bad_name, "key_count": 1}]
    )
    fake = _Cp949Stdout()
    monkeypatch.setattr(cli.sys, "stdout", fake)

    assert cli.main(["collections"]) == 0  # UnicodeEncodeError 없이 통과
    assert fake.written  # 무언가는 출력됐다
