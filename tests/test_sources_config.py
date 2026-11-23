"""[sources] in config.toml, environment over file, what is missing (R1, R2)."""

import pytest

from rolecard import config as cfg
from rolecard.sources import enabled, key_origin, source_settings, status


def settings(**sources):
    return cfg.validate_config({"sources": sources})


def test_defaults_enable_the_keyless_sources():
    assert enabled(cfg.DEFAULTS) == ["remotive", "arbeitnow"]


def test_unknown_source_or_country_is_a_config_error():
    with pytest.raises(cfg.ConfigError, match="sources.enabled"):
        settings(enabled="remotive,jooble")
    with pytest.raises(cfg.ConfigError, match="adzuna_country"):
        settings(adzuna_country="xx")


def test_env_overrides_file_and_origin_is_reported():
    s = settings(enabled="adzuna", adzuna_app_id="file-id", adzuna_app_key="")
    env = {cfg.ENV_ADZUNA_KEY: "env-key"}
    merged = source_settings(s, env)
    assert merged["adzuna_app_id"] == "file-id" and merged["adzuna_app_key"] == "env-key"
    assert key_origin(s, "adzuna_app_key", env) == "env"
    assert key_origin(s, "adzuna_app_id", env) == "file"
    assert key_origin(s, "adzuna_app_key", {}) == ""


def test_status_lists_missing_keys(monkeypatch):
    monkeypatch.delenv(cfg.ENV_ADZUNA_ID, raising=False)
    monkeypatch.delenv(cfg.ENV_ADZUNA_KEY, raising=False)
    rows = {r["name"]: r for r in status(settings(enabled="remotive,adzuna"))}
    assert rows["adzuna"]["enabled"] and rows["adzuna"]["missing"] == [
        "adzuna_app_id", "adzuna_app_key"]
    assert not rows["arbeitnow"]["enabled"] and rows["remotive"]["missing"] == []


def test_keys_round_trip_through_the_file(tmp_path):
    s = settings(adzuna_app_id="a\"b", adzuna_app_key="k\\1")
    cfg.save_config(tmp_path, s)
    assert cfg.load_config(tmp_path)["sources"]["adzuna_app_key"] == "k\\1"
