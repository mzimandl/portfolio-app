"""Application settings loaded from a TOML file."""

import os
import re
import tomllib
from dataclasses import dataclass
from pathlib import Path

CONFIG_ENV_VAR = "PORTFOLIO_CONFIG"
DEFAULT_CONFIG_NAME = "config.toml"

_CURRENCY_RE = re.compile(r"^[A-Z]{3}$")


class ConfigError(Exception):
    """The config file is missing or invalid."""


@dataclass(frozen=True)
class Config:
    db_path: Path
    base_currency: str
    locale: str
    benchmark: str | None = None
    # Instrument types reported apart from the investments (e.g. savings accounts).
    separate_types: tuple[str, ...] = ()
    # Dated copies of the database: where, and how many to keep (0 = make none).
    backup_dir: Path | None = None
    backup_keep: int = 30
    # Rules the tax overview applies: how long a holding has to be held for its sale to be
    # exempt, the yearly proceeds up to which sales are exempt, and which types are crypto
    # (the limit counts for them apart from the securities).
    tax_holding_years: int = 3
    tax_proceeds_limit: int = 100_000
    tax_crypto_types: tuple[str, ...] = ("crypto",)


def resolve_config_path(path: str | Path | None = None) -> Path:
    """Explicit path, then $PORTFOLIO_CONFIG, then ./config.toml."""
    if path is not None:
        return Path(path)
    return Path(os.environ.get(CONFIG_ENV_VAR) or DEFAULT_CONFIG_NAME)


def load_config(path: str | Path | None = None) -> Config:
    config_path = resolve_config_path(path)
    try:
        with config_path.open("rb") as f:
            data = tomllib.load(f)
    except FileNotFoundError:
        raise ConfigError(
            f"Config file not found: {config_path.resolve()}. "
            "Copy config.sample.toml to config.toml."
        ) from None
    except tomllib.TOMLDecodeError as e:
        raise ConfigError(f"Invalid TOML in {config_path}: {e}") from e

    def text(key: str, *, required: bool = True) -> str | None:
        value = data.get(key)
        if value is None:
            if required:
                raise ConfigError(f"Missing '{key}' in {config_path}")
            return None
        if not isinstance(value, str) or not value.strip():
            raise ConfigError(f"'{key}' in {config_path} must be a non-empty string")
        return value.strip()

    base_currency = text("base_currency")
    if not _CURRENCY_RE.match(base_currency):
        raise ConfigError(
            f"'base_currency' must be a 3-letter uppercase code, got '{base_currency}'"
        )

    # A relative db path is relative to the config file, not the working directory.
    db_path = (config_path.parent / Path(text("db")).expanduser()).resolve()

    separate_types = data.get("separate_types", [])
    if not isinstance(separate_types, list) or not all(
        isinstance(name, str) and name.strip() for name in separate_types
    ):
        raise ConfigError(f"'separate_types' in {config_path} must be a list of type names")

    def whole_number(key: str, default: int) -> int:
        value = data.get(key, default)
        if isinstance(value, bool) or not isinstance(value, int) or value < 0:
            raise ConfigError(f"'{key}' in {config_path} must be a whole number, 0 or more")
        return value

    crypto_types = data.get("tax_crypto_types", ["crypto"])
    if not isinstance(crypto_types, list) or not all(isinstance(n, str) for n in crypto_types):
        raise ConfigError(f"'tax_crypto_types' in {config_path} must be a list of type names")

    backup_keep = data.get("backup_keep", 30)
    if isinstance(backup_keep, bool) or not isinstance(backup_keep, int) or backup_keep < 0:
        raise ConfigError(f"'backup_keep' in {config_path} must be a whole number, 0 or more")
    # Next to the database unless told otherwise; relative paths are relative to the config.
    backup_dir = (
        (config_path.parent / Path(text("backup_dir")).expanduser()).resolve()
        if "backup_dir" in data
        else db_path.parent / "backups"
    )

    return Config(
        db_path=db_path,
        base_currency=base_currency,
        locale=text("locale"),
        benchmark=text("benchmark", required=False),
        separate_types=tuple(name.strip() for name in separate_types),
        backup_dir=backup_dir,
        backup_keep=backup_keep,
        tax_holding_years=whole_number("tax_holding_years", 3),
        tax_proceeds_limit=whole_number("tax_proceeds_limit", 100_000),
        tax_crypto_types=tuple(name.strip() for name in crypto_types),
    )
