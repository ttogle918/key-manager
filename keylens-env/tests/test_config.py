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
