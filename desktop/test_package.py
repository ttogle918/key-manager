# SPDX-FileCopyrightText: 2026 [Your Name]
# SPDX-License-Identifier: MIT
"""package.py 의 배포 위생 가드 테스트.

이 가드가 막는 사고: 패키징된 앱은 금고를 exe 옆에 만들기 때문에, 빌드한 exe 를 한 번
실행해 보는 것만으로 vault.db 가 산출물 안에 생긴다. 그대로 압축하면 금고가 배포된다.
"""
import sqlite3
import zipfile

import pytest

import package


def _make_vault(path, *, initialized: bool) -> None:
    conn = sqlite3.connect(path)
    conn.executescript("CREATE TABLE meta (id INTEGER PRIMARY KEY, salt BLOB)")
    if initialized:
        conn.execute("INSERT INTO meta (id, salt) VALUES (1, X'00')")
    conn.commit()
    conn.close()


def test_sanitize_removes_empty_vault(tmp_path):
    """스모크 테스트로 생긴 빈 금고는 조용히 걸러낸다 - 흔한 경우라 사람을 막을 이유가 없다."""
    (tmp_path / "KeyLens.exe").write_bytes(b"stub")
    vault = tmp_path / "vault.db"
    _make_vault(vault, initialized=False)

    removed = package.sanitize(tmp_path)

    assert not vault.exists()
    assert [p.name for p in removed] == ["vault.db"]
    assert (tmp_path / "KeyLens.exe").exists()


def test_sanitize_refuses_to_delete_a_real_vault(tmp_path):
    """내용이 든 금고는 지우지 않고 멈춘다 - 자동 삭제는 그 자체가 데이터 사고다."""
    vault = tmp_path / "vault.db"
    _make_vault(vault, initialized=True)

    with pytest.raises(SystemExit) as e:
        package.sanitize(tmp_path)

    assert "중단" in str(e.value)
    assert vault.exists(), "사용자 금고를 지우면 안 된다"


def test_sanitize_removes_journals_and_env(tmp_path):
    for name in ("vault.db-wal", "vault.db-shm", ".env"):
        (tmp_path / name).write_text("x", encoding="utf-8")
    # 남은 sqlite 는 실제 db 로 만든다. 저널·.env 와 달리 db 본체는 내용 검사를 거치므로,
    # 텍스트 파일로 흉내내면 "열 수 없는 db"가 되어 아래 abort 케이스와 섞인다.
    sqlite3.connect(tmp_path / "leftover.sqlite").close()

    removed = {p.name for p in package.sanitize(tmp_path)}

    assert removed == {"vault.db-wal", "vault.db-shm", ".env", "leftover.sqlite"}


def test_sanitize_stops_on_a_db_it_cannot_read(tmp_path):
    """열리지 않는 db 는 지우지 않고 멈춘다.

    앱이 아직 실행 중이면 금고가 잠겨 읽기에 실패할 수 있다. 그 상황에서 "못 읽었으니
    비었겠지"라고 지우면 진짜 금고를 날린다. 판단이 안 서면 사람에게 넘긴다.
    """
    broken = tmp_path / "vault.db"
    broken.write_bytes(b"not a sqlite file at all")

    with pytest.raises(SystemExit):
        package.sanitize(tmp_path)

    assert broken.exists()


def test_sanitize_reaches_into_subdirectories(tmp_path):
    nested = tmp_path / "lib" / "data"
    nested.mkdir(parents=True)
    _make_vault(nested / "vault.db", initialized=False)

    removed = package.sanitize(tmp_path)

    assert [str(p).replace("\\", "/") for p in removed] == ["lib/data/vault.db"]


def test_audit_zip_deletes_a_zip_that_still_has_secrets(tmp_path):
    """마지막 방어선 - 어떤 경로로든 비밀이 남았으면 zip 을 내보내지 않는다."""
    zip_path = tmp_path / "KeyLens-vX-win64.zip"
    with zipfile.ZipFile(zip_path, "w") as zf:
        zf.writestr("KeyLens.exe", "stub")
        zf.writestr("vault.db", "secret")

    with pytest.raises(SystemExit) as e:
        package.audit_zip(zip_path)

    assert "중단" in str(e.value)
    assert not zip_path.exists(), "위험한 zip 은 남겨두면 안 된다"


def test_audit_zip_passes_clean_archive(tmp_path):
    zip_path = tmp_path / "clean.zip"
    with zipfile.ZipFile(zip_path, "w") as zf:
        zf.writestr("KeyLens.exe", "stub")
        zf.writestr("frontend/dist/index.html", "<html>")

    package.audit_zip(zip_path)

    assert zip_path.exists()


def test_version_comes_from_setup_py():
    """버전 출처가 하나여야 zip 이름과 앱 버전이 어긋나지 않는다."""
    v = package._read_version()

    assert v.count(".") == 2, v


def test_build_stage_dir_ignores_stale_sibling_dirs(tmp_path, monkeypatch):
    """예전 실험 디렉토리가 남아 있어도 이번 파이썬으로 만든 산출물만 고른다.

    회귀 방지: glob("exe.*") 로 고르던 초안은 build/ 에 몇 달 묵은
    exe.win-amd64-3.13-v2 가 있으면 멈추거나(운이 좋으면) 그 옛날 앱을 배포했다.
    """
    import sys as _sys
    import sysconfig as _sysconfig

    monkeypatch.setattr(package, "BUILD", tmp_path)
    expected = f"exe.{_sysconfig.get_platform()}-{_sys.version_info.major}.{_sys.version_info.minor}"
    (tmp_path / expected).mkdir()
    (tmp_path / f"{expected}-v2").mkdir()
    (tmp_path / "exe.win32-3.9").mkdir()

    assert package.build_stage_dir() == tmp_path / expected


def test_build_stage_dir_errors_when_nothing_built(tmp_path, monkeypatch):
    monkeypatch.setattr(package, "BUILD", tmp_path)

    with pytest.raises(SystemExit) as e:
        package.build_stage_dir()

    assert "setup.py build" in str(e.value)
