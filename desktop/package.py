# SPDX-FileCopyrightText: 2026 [Your Name]
# SPDX-License-Identifier: MIT
"""릴리스 아티팩트(zip) 생성 - 빌드 산출물에서 금고/비밀 파일을 걷어낸 뒤 압축한다.

왜 별도 스크립트인가: `setup.py build` 만으로는 배포물이 안전하지 않다. 패키징된 앱은
**금고를 exe 옆에 만든다**(app.py 의 KEYLENS_VAULT_PATH). 그래서 빌드한 exe 를 한 번이라도
실행해 보면(= 정상적인 스모크 테스트) 바로 그 자리에 vault.db 가 생기고, 그대로 압축하면
**사용자 금고가 배포물에 실려 나간다.** 키 관리 도구에서 이건 가장 나쁜 사고라서, 압축 전
검사를 사람 기억이 아니라 스크립트에 박아 둔다.

사용법:
    cd desktop && python package.py            # build/ 를 그대로 쓰고 압축만
    cd desktop && python package.py --build    # setup.py build 부터 다시

사전 준비는 desktop/README.md 참고(프론트 빌드 + requirements-build.txt 설치).
"""
from __future__ import annotations

import argparse
import shutil
import sqlite3
import subprocess
import sys
import sysconfig
import zipfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
BUILD = HERE / "build"

# 배포물에 절대 들어가면 안 되는 파일들. 금고 본체와 SQLite 저널, 그리고 실수로 흘러든 .env.
SECRET_GLOBS = ("vault.db", "vault.db-wal", "vault.db-shm", "*.sqlite", "*.sqlite3", ".env")


def _read_version() -> str:
    """setup.py 의 version= 을 단일 출처로 삼는다(두 곳에 적어 어긋나는 걸 막는다)."""
    for line in (HERE / "setup.py").read_text(encoding="utf-8").splitlines():
        s = line.strip()
        if s.startswith("version="):
            return s.split('"')[1]
    raise SystemExit("setup.py 에서 version= 을 찾지 못했습니다")


def _is_real_vault(path: Path) -> bool:
    """meta 테이블에 행이 있으면 진짜 금고다(vault_repo.is_initialized 와 같은 판단)."""
    try:
        conn = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
    except sqlite3.Error:
        return False
    try:
        row = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='meta'"
        ).fetchone()
        if row is None:
            return False
        return conn.execute("SELECT 1 FROM meta WHERE id = 1").fetchone() is not None
    except sqlite3.Error:
        # 읽을 수 없는 파일은 안전한 쪽으로 - 진짜 금고로 취급해 사람이 보게 만든다.
        return True
    finally:
        conn.close()


def build_stage_dir() -> Path:
    """`setup.py build` 가 만드는 산출물 디렉토리를 **계산해서** 찾는다.

    glob("exe.*") 로 고르지 않는 이유: build/ 에는 예전 실험이나 다른 파이썬 버전으로 만든
    디렉토리가 남아 있을 수 있다(실제로 몇 달 묵은 exe.win-amd64-3.13-v2 가 있었다).
    릴리스 스크립트가 그중 엉뚱한 걸 집으면 **오래된 앱이 배포된다** - 조용히 일어나는데
    피해는 큰 사고라, 이름을 추측하지 않고 cx_Freeze 와 같은 규칙으로 직접 만든다.
    """
    name = f"exe.{sysconfig.get_platform()}-{sys.version_info.major}.{sys.version_info.minor}"
    stage = BUILD / name
    if not stage.is_dir():
        raise SystemExit(
            f"빌드 산출물이 없습니다: {stage}\n"
            "  먼저 `python package.py --build` 또는 `python setup.py build` 를 실행하세요."
        )
    return stage


def sanitize(stage: Path) -> list[Path]:
    """압축 대상에서 비밀 파일을 제거한다. 내용이 든 금고면 지우지 않고 멈춘다."""
    removed = []
    for pattern in SECRET_GLOBS:
        for found in sorted(stage.rglob(pattern)):
            # 진짜 금고 검사는 db 본체에만 한다. 저널(-wal/-shm)과 .env 는 그 자체로
            # 금고가 아니고 sqlite 로 열리지도 않아서, 여기 걸리면 안전측 판정에
            # 걸려 빌드가 멈춰버린다(그냥 지우는 게 맞는 파일들이다).
            is_db = found.name == "vault.db" or found.suffix in (".sqlite", ".sqlite3")
            if is_db and _is_real_vault(found):
                raise SystemExit(
                    f"중단: 내용이 있는 금고가 빌드 산출물에 있습니다 - {found}\n"
                    "  배포 사고를 막기 위해 자동으로 지우지 않습니다. 안에 남길 게 없는지\n"
                    "  직접 확인한 뒤 파일을 지우고 다시 실행하세요."
                )
            found.unlink()
            removed.append(found.relative_to(stage))
    return removed


def audit_zip(zip_path: Path) -> None:
    """마지막 방어선 - 완성된 zip 을 다시 열어 비밀 파일이 없는지 확인한다."""
    import fnmatch

    with zipfile.ZipFile(zip_path) as zf:
        names = zf.namelist()
    bad = [
        n for n in names
        if any(fnmatch.fnmatch(Path(n).name, pat) for pat in SECRET_GLOBS)
    ]
    if bad:
        zip_path.unlink()
        raise SystemExit(f"중단: zip 에 비밀 파일이 남아 있습니다 - {bad} (zip 을 삭제했습니다)")
    print(f"  zip 검사 통과: {len(names)}개 항목, 비밀 파일 0건")


def main() -> None:
    ap = argparse.ArgumentParser(description="KeyLens 릴리스 zip 생성")
    ap.add_argument("--build", action="store_true", help="setup.py build 부터 다시 실행")
    args = ap.parse_args()

    version = _read_version()

    if args.build:
        print(f"[1/4] setup.py build (v{version})")
        subprocess.run([sys.executable, "setup.py", "build"], cwd=HERE, check=True)
    else:
        print(f"[1/4] 기존 build/ 사용 (v{version})")

    stage = build_stage_dir()

    print(f"[2/4] 위생 검사: {stage.name}")
    removed = sanitize(stage)
    if removed:
        for r in removed:
            print(f"  제외: {r}")
    else:
        print("  걸러낼 파일 없음")

    zip_path = BUILD / f"KeyLens-v{version}-win64.zip"
    print(f"[3/4] 압축: {zip_path.name}")
    if zip_path.exists():
        zip_path.unlink()
    base = zip_path.with_suffix("")
    shutil.make_archive(str(base), "zip", root_dir=stage)

    print("[4/4] 최종 확인")
    audit_zip(zip_path)
    size_mb = zip_path.stat().st_size / 1024 / 1024
    print(f"\n완료: {zip_path}  ({size_mb:.1f} MB)")


if __name__ == "__main__":
    main()
