"""Data folder, config.toml and secret key.

The config file has a fixed, small schema, so it is written by hand here instead of
pulling in a TOML writer dependency. Reading uses the stdlib ``tomllib``.
"""

from __future__ import annotations

import os
import secrets
import tomllib
from copy import deepcopy
from pathlib import Path

CONFIG_FILE = "config.toml"
SECRET_FILE = "secret_key"
DB_FILE = "rolecard.sqlite3"
ENV_HOME = "ROLECARD_HOME"
ENV_API_KEY = "ROLECARD_OPENAI_API_KEY"
ENV_ADZUNA_ID = "ROLECARD_ADZUNA_APP_ID"
ENV_ADZUNA_KEY = "ROLECARD_ADZUNA_APP_KEY"

PROVIDERS = ("auto", "claude", "openai", "none")
LANGUAGES = ("", "en", "es")
THEMES = ("system", "light", "dark")
SOURCE_NAMES = ("remotive", "arbeitnow", "adzuna")
ADZUNA_COUNTRIES = ("at", "au", "be", "br", "ca", "ch", "de", "es", "fr", "gb", "in", "it",
                    "mx", "nl", "nz", "pl", "sg", "us", "za")

DEFAULTS: dict[str, dict[str, object]] = {
    "ai": {"provider": "auto", "base_url": "", "model": "", "api_key": "", "timeout": 120},
    "ui": {"language": "", "theme": "system"},
    "sources": {"enabled": "remotive,arbeitnow", "adzuna_app_id": "", "adzuna_app_key": "",
                "adzuna_country": "es"},
}


class ConfigError(Exception):
    """A configuration problem the user can fix; its message is one readable line."""


def resolve_data_dir(cli_value: str | None, env: dict[str, str] | None = None) -> Path:
    """Pick the data folder: --data-dir, then ROLECARD_HOME, then ~/.rolecard."""
    env = os.environ if env is None else env
    raw = cli_value or env.get(ENV_HOME) or str(Path.home() / ".rolecard")
    return Path(raw).expanduser().resolve()


def ensure_data_dir(data_dir: Path) -> Path:
    """Create the data folder (private to the user where the OS allows it)."""
    try:
        data_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
    except OSError as exc:
        raise ConfigError(f"cannot create data folder {data_dir}: {exc.strerror}") from exc
    if not data_dir.is_dir():
        raise ConfigError(f"data folder {data_dir} is not a folder")
    return data_dir


def load_config(data_dir: Path) -> dict[str, dict[str, object]]:
    """Read config.toml, creating it with the defaults the first time."""
    path = data_dir / CONFIG_FILE
    if not path.exists():
        save_config(data_dir, DEFAULTS)
        return deepcopy(DEFAULTS)
    try:
        raw = tomllib.loads(path.read_text(encoding="utf-8"))
    except tomllib.TOMLDecodeError as exc:
        raise ConfigError(f"{path} is not valid TOML: {exc}") from exc
    except (OSError, UnicodeDecodeError) as exc:
        raise ConfigError(f"cannot read {path}: {exc}") from exc
    return validate_config(raw, path)


def validate_config(raw: dict, path: Path | str = CONFIG_FILE) -> dict[str, dict[str, object]]:
    """Merge ``raw`` over the defaults, rejecting wrong types and unknown choices."""
    cfg = deepcopy(DEFAULTS)
    for section, values in raw.items():
        if section not in cfg:
            continue  # unknown sections are ignored so newer files still load
        if not isinstance(values, dict):
            raise ConfigError(f"{path}: [{section}] must be a table")
        for key, value in values.items():
            if key not in cfg[section]:
                continue
            _check_value(section, key, value, cfg[section][key], path)
            cfg[section][key] = value
    return cfg


def _check_value(section: str, key: str, value: object, default: object, path) -> None:
    where = f"{path}: {section}.{key}"
    if isinstance(default, int):
        if not isinstance(value, int) or isinstance(value, bool) or not 1 <= value <= 3600:
            raise ConfigError(f"{where} must be a whole number of seconds between 1 and 3600")
        return
    if not isinstance(value, str):
        raise ConfigError(f"{where} must be text")
    if (section, key) == ("ai", "provider") and value not in PROVIDERS:
        raise ConfigError(f"{where} must be one of: {', '.join(PROVIDERS)}")
    if (section, key) == ("ui", "language") and value not in LANGUAGES:
        raise ConfigError(f"{where} must be \"en\", \"es\" or empty")
    if (section, key) == ("ui", "theme") and value not in THEMES:
        raise ConfigError(f"{where} must be one of: {', '.join(THEMES)}")
    if (section, key) == ("sources", "enabled") and not set(split_list(value)) <= set(
            SOURCE_NAMES):
        raise ConfigError(f"{where} must list some of: {', '.join(SOURCE_NAMES)}")
    if (section, key) == ("sources", "adzuna_country") and value not in ADZUNA_COUNTRIES:
        raise ConfigError(f"{where} must be one of: {', '.join(ADZUNA_COUNTRIES)}")


def split_list(value: str) -> list[str]:
    """``"a, b,,c"`` -> ``["a", "b", "c"]`` (comma-separated config and form lists)."""
    return [part.strip() for part in value.split(",") if part.strip()]


def save_config(data_dir: Path, cfg: dict[str, dict[str, object]]) -> None:
    """Write config.toml atomically (temp file + replace)."""
    validate_config(cfg)
    path = data_dir / CONFIG_FILE
    tmp = path.with_suffix(".toml.tmp")
    tmp.write_text(dump_toml(cfg), encoding="utf-8")
    tmp.chmod(0o600)  # may hold API keys
    os.replace(tmp, path)


def dump_toml(cfg: dict[str, dict[str, object]]) -> str:
    """Serialise the fixed two-level config schema (strings and integers only)."""
    lines = ["# rolecard settings. Edit here or in the Settings page.", ""]
    for section in DEFAULTS:
        lines.append(f"[{section}]")
        for key in DEFAULTS[section]:
            value = cfg.get(section, {}).get(key, DEFAULTS[section][key])
            lines.append(f"{key} = {_toml_value(value)}")
        lines.append("")
    return "\n".join(lines)


def _toml_value(value: object) -> str:
    if isinstance(value, int) and not isinstance(value, bool):
        return str(value)
    out = []
    for ch in str(value):
        if ch == "\\":
            out.append("\\\\")
        elif ch == '"':
            out.append('\\"')
        elif ord(ch) < 0x20 or ord(ch) == 0x7F:
            out.append(f"\\u{ord(ch):04x}")
        else:
            out.append(ch)
    return '"' + "".join(out) + '"'


def load_secret_key(data_dir: Path) -> str:
    """Return the session secret, generating it on first run."""
    path = data_dir / SECRET_FILE
    if path.exists():
        key = path.read_text(encoding="utf-8").strip()
        if len(key) >= 32:
            return key
    key = secrets.token_hex(32)
    path.write_text(key, encoding="utf-8")
    try:
        path.chmod(0o600)
    except OSError:
        pass
    return key
