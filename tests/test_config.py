import tomllib

import pytest

from rolecard import config as cfg


def test_data_dir_precedence(tmp_path):
    env = {cfg.ENV_HOME: str(tmp_path / "env")}
    assert cfg.resolve_data_dir(str(tmp_path / "cli"), env) == (tmp_path / "cli").resolve()
    assert cfg.resolve_data_dir(None, env) == (tmp_path / "env").resolve()
    assert cfg.resolve_data_dir(None, {}).name == ".rolecard"


def test_first_run_writes_defaults(tmp_path):
    cfg.ensure_data_dir(tmp_path / "d")
    loaded = cfg.load_config(tmp_path / "d")
    assert loaded == cfg.DEFAULTS
    on_disk = tomllib.loads((tmp_path / "d" / cfg.CONFIG_FILE).read_text(encoding="utf-8"))
    assert on_disk["ai"]["provider"] == "auto"
    assert on_disk["ai"]["timeout"] == 120


def test_round_trip_escapes_strings(tmp_path):
    data = {
        "ai": {
            "provider": "openai",
            "base_url": "http://localhost:11434/v1",
            "model": 'we"ird\\model\nx',
            "api_key": "sk-ñ",
            "timeout": 30,
        },
        "ui": {"language": "es", "theme": "dark"},
    }
    cfg.save_config(tmp_path, data)
    assert cfg.load_config(tmp_path) == {**data, "sources": cfg.DEFAULTS["sources"]}


def test_partial_file_gets_defaults_and_unknown_keys_are_ignored(tmp_path):
    (tmp_path / cfg.CONFIG_FILE).write_text('[ai]\nmodel = "m"\nfoo = 1\n[other]\nx = 1\n')
    loaded = cfg.load_config(tmp_path)
    assert loaded["ai"]["model"] == "m"
    assert loaded["ai"]["provider"] == "auto"
    assert "foo" not in loaded["ai"]


@pytest.mark.parametrize(
    "content, fragment",
    [
        ("[ai\nprovider = 1", "not valid TOML"),
        ('[ai]\nprovider = "gpt"', "must be one of"),
        ('[ai]\ntimeout = "10"', "whole number"),
        ("[ai]\ntimeout = 0", "whole number"),
        ("[ai]\nmodel = 3", "must be text"),
        ('ai = "x"', "must be a table"),
        ('[ui]\nlanguage = "fr"', "language"),
        ('[ui]\ntheme = "blue"', "ui.theme must be one of"),
    ],
)
def test_bad_config_is_one_line_error(tmp_path, content, fragment):
    (tmp_path / cfg.CONFIG_FILE).write_text(content)
    with pytest.raises(cfg.ConfigError) as info:
        cfg.load_config(tmp_path)
    assert fragment in str(info.value)
    assert "\n" not in str(info.value).strip()


def test_secret_key_is_created_once(tmp_path):
    first = cfg.load_secret_key(tmp_path)
    assert len(first) == 64
    assert cfg.load_secret_key(tmp_path) == first


def test_data_dir_that_is_a_file_fails(tmp_path):
    target = tmp_path / "file"
    target.write_text("x")
    with pytest.raises(cfg.ConfigError):
        cfg.ensure_data_dir(target)
