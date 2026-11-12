from pathlib import Path

import pytest

from portfolio.core.config import CONFIG_ENV_VAR, ConfigError, load_config

VALID = 'db = "data/p.db"\nbase_currency = "CZK"\nlocale = "cs"\n'


def write(tmp_path: Path, content: str) -> Path:
    path = tmp_path / "config.toml"
    path.write_text(content)
    return path


def test_loads_valid_config(tmp_path):
    config = load_config(write(tmp_path, VALID))
    assert config.base_currency == "CZK"
    assert config.locale == "cs"
    assert config.benchmark is None


def test_relative_db_path_is_relative_to_config_file(tmp_path, monkeypatch):
    path = write(tmp_path, VALID)
    monkeypatch.chdir("/")
    assert load_config(path).db_path == tmp_path / "data" / "p.db"


def test_absolute_db_path_is_kept(tmp_path):
    path = write(tmp_path, VALID.replace("data/p.db", "/somewhere/p.db"))
    assert load_config(path).db_path == Path("/somewhere/p.db")


def test_backups_go_next_to_the_database_unless_told_otherwise(tmp_path):
    config = load_config(write(tmp_path, VALID))
    assert (config.backup_dir, config.backup_keep) == (tmp_path / "data" / "backups", 30)
    config = load_config(write(tmp_path, VALID + 'backup_dir = "copies"\nbackup_keep = 0\n'))
    assert (config.backup_dir, config.backup_keep) == (tmp_path / "copies", 0)
    for bad in ("-1", '"many"', "true", "1.5"):
        with pytest.raises(ConfigError, match="backup_keep"):
            load_config(write(tmp_path, VALID + f"backup_keep = {bad}\n"))


def test_benchmark_is_optional(tmp_path):
    config = load_config(write(tmp_path, VALID + 'benchmark = "VWCE.DE"\n'))
    assert config.benchmark == "VWCE.DE"


def test_path_from_environment(tmp_path, monkeypatch):
    monkeypatch.setenv(CONFIG_ENV_VAR, str(write(tmp_path, VALID)))
    assert load_config().base_currency == "CZK"


def test_missing_file(tmp_path):
    with pytest.raises(ConfigError, match="not found"):
        load_config(tmp_path / "nope.toml")


def test_invalid_toml(tmp_path):
    with pytest.raises(ConfigError, match="Invalid TOML"):
        load_config(write(tmp_path, "db = "))


@pytest.mark.parametrize("key", ["db", "base_currency", "locale"])
def test_missing_required_key(tmp_path, key):
    content = "\n".join(line for line in VALID.splitlines() if not line.startswith(key))
    with pytest.raises(ConfigError, match=key):
        load_config(write(tmp_path, content))


@pytest.mark.parametrize("value", ["czk", "CZ", "KORUNA"])
def test_rejects_bad_currency(tmp_path, value):
    with pytest.raises(ConfigError, match="base_currency"):
        load_config(write(tmp_path, VALID.replace("CZK", value)))


def test_sample_config_is_valid():
    sample = Path(__file__).parent.parent / "config.sample.toml"
    assert load_config(sample).base_currency == "CZK"


def test_separate_types(tmp_path):
    assert load_config(write(tmp_path, VALID)).separate_types == ()
    config = load_config(write(tmp_path, VALID + 'separate_types = ["savings", " pension "]\n'))
    assert config.separate_types == ("savings", "pension")
    for bad in ('"savings"', "[1]", '[""]'):
        with pytest.raises(ConfigError, match="separate_types"):
            load_config(write(tmp_path, VALID + f"separate_types = {bad}\n"))
