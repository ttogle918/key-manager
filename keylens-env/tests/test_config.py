# SPDX-FileCopyrightText: 2026 [Your Name]
# SPDX-License-Identifier: MIT
"""config.py — .keylens.toml 상위 탐색(python-dotenv의 find_dotenv()와 같은 방식)."""
import pytest

from keylens_env.config import find_config
from keylens_env.exceptions import KeylensConfigError


def test_find_config_in_start_dir(tmp_path):
    (tmp_path / ".keylens.toml").write_text('project = "블로그"\n', encoding="utf-8")
    project, config_dir = find_config(tmp_path)
    assert project == "블로그"
    assert config_dir == tmp_path


def test_find_config_searches_upward(tmp_path):
    (tmp_path / ".keylens.toml").write_text('project = "블로그"\n', encoding="utf-8")
    nested = tmp_path / "a" / "b" / "c"
    nested.mkdir(parents=True)
    project, config_dir = find_config(nested)
    assert project == "블로그"
    assert config_dir == tmp_path


def test_find_config_not_found_raises(tmp_path):
    empty = tmp_path / "no-config-here"
    empty.mkdir()
    with pytest.raises(KeylensConfigError):
        find_config(empty)


def test_find_config_missing_project_key_raises(tmp_path):
    (tmp_path / ".keylens.toml").write_text('other_key = "값"\n', encoding="utf-8")
    with pytest.raises(KeylensConfigError):
        find_config(tmp_path)


def test_find_config_malformed_toml_raises(tmp_path):
    (tmp_path / ".keylens.toml").write_text("이건 toml이 아님 {{{\n", encoding="utf-8")
    with pytest.raises(KeylensConfigError):
        find_config(tmp_path)


def test_find_config_blank_project_value_raises(tmp_path):
    (tmp_path / ".keylens.toml").write_text('project = "   "\n', encoding="utf-8")
    with pytest.raises(KeylensConfigError):
        find_config(tmp_path)


# ── 회귀: Windows 메모장 저장 인코딩 ──
# 발단: read_text(encoding="utf-8") 고정이라 BOM 붙은 파일은 "TOML 형식이 아니에요"라는
# 엉뚱한 오류가 났고, UTF-16 파일은 원시 UnicodeDecodeError가 그대로 밖으로 샜다.


def test_finds_config_saved_with_utf8_bom(tmp_path):
    """메모장 'UTF-8'(BOM 포함) 저장분도 그냥 읽혀야 한다."""
    (tmp_path / ".keylens.toml").write_bytes('collection = "블로그"\n'.encode("utf-8-sig"))
    name, directory = find_config(tmp_path)
    assert name == "블로그"
    assert directory == tmp_path


def test_utf16_config_raises_typed_config_error(tmp_path):
    """메모장 '유니코드'(UTF-16) 저장분은 원시 UnicodeDecodeError가 아니라 안내 메시지로."""
    (tmp_path / ".keylens.toml").write_bytes('collection = "블로그"\n'.encode("utf-16"))
    with pytest.raises(KeylensConfigError) as exc:
        find_config(tmp_path)
    assert "UTF-8" in str(exc.value)


def test_legacy_project_key_still_works(tmp_path):
    """예전 문서대로 project = 로 써 둔 파일이 깨지면 안 된다."""
    (tmp_path / ".keylens.toml").write_text('project = "블로그"\n', encoding="utf-8")
    assert find_config(tmp_path)[0] == "블로그"


def test_collection_key_wins_over_project(tmp_path):
    (tmp_path / ".keylens.toml").write_text(
        'collection = "새이름"\nproject = "옛이름"\n', encoding="utf-8"
    )
    assert find_config(tmp_path)[0] == "새이름"
