from pathlib import Path

import pytest

from app.config import Settings
from app.sources.majsoul.fetch_config import MajsoulConfigError, load_majsoul_fetch_config


def test_loads_ordered_accounts_and_defaults_host(tmp_path: Path):
    path = tmp_path / "config.toml"
    path.write_text(
        "timeout_seconds = 12\n"
        "[[accounts]]\n"
        'username = "first"\n'
        'password = "secret-one"\n'
        "[[accounts]]\n"
        'username = "second"\n'
        'password = "secret-two"\n'
        'host = "https://game.maj-soul.com"\n',
        encoding="utf-8",
    )

    config = load_majsoul_fetch_config(path)

    assert config.timeout_seconds == 12
    assert [account.username for account in config.accounts] == ["first", "second"]
    assert all(account.host == "https://game.maj-soul.com" for account in config.accounts)
    assert config.accounts[0].password.get_secret_value() == "secret-one"
    assert "secret-one" not in repr(config)
    assert "secret-two" not in repr(config)


def test_loads_majsoul_and_admin_settings_from_one_file(tmp_path: Path):
    from app.config_file import load_haiun_config

    path = tmp_path / "config.toml"
    path.write_text(
        "timeout_seconds = 12\n"
        "[[accounts]]\n"
        'username = "first"\n'
        'password = "secret-one"\n'
        "[admin]\n"
        'password = "admin-secret-long"\n'
        "session_hours = 18\n",
        encoding="utf-8",
    )

    config = load_haiun_config(path)

    assert config.admin is not None
    assert config.admin.password.get_secret_value() == "admin-secret-long"
    assert config.admin.session_hours == 18
    assert config.majsoul.accounts[0].username == "first"
    assert "admin-secret-long" not in repr(config)
    assert "secret-one" not in repr(config)


def test_missing_optional_file_locks_admin_and_leaves_majsoul_unconfigured(tmp_path: Path):
    from app.config_file import load_haiun_config

    config = load_haiun_config(tmp_path / "missing.toml", missing_ok=True)

    assert config.admin is None
    assert config.accounts == ()


@pytest.mark.parametrize(
    "text",
    [
        "",
        "timeout_seconds = 0\n",
        "[[accounts]]\nusername = 'x'\n",
        "[[accounts]]\nusername = 'x'\npassword = 'y'\nhost = 'https://example.com'\n",
        "[[accounts]]\nusername = 'x'\npassword = 'y'\nhost = 'https://game.maj-soul.com:8443'\n",
        "[[accounts]]\nusername = 'x'\npassword = 'y'\nhost = 'https://game.maj-soul.com?next=x'\n",
    ],
)
def test_rejects_missing_or_invalid_accounts(tmp_path: Path, text: str):
    path = tmp_path / "config.toml"
    path.write_text(text, encoding="utf-8")

    with pytest.raises(MajsoulConfigError) as error:
        load_majsoul_fetch_config(path)

    assert "password" not in str(error.value).lower()
    assert "username" not in str(error.value).lower()


def test_missing_config_error_contains_path_but_no_secret(tmp_path: Path):
    path = tmp_path / "missing.toml"

    with pytest.raises(MajsoulConfigError) as error:
        load_majsoul_fetch_config(path)

    assert str(path) in str(error.value)


def test_invalid_config_discards_raw_validation_cause_and_hides_account_repr(tmp_path: Path):
    invalid = tmp_path / "invalid.toml"
    invalid.write_text("[[accounts]]\nusername = 'visible-user'\npassword = 123456789\n", encoding="utf-8")

    with pytest.raises(MajsoulConfigError) as error:
        load_majsoul_fetch_config(invalid)

    assert error.value.__cause__ is None

    valid = tmp_path / "valid.toml"
    valid.write_text("[[accounts]]\nusername = 'visible-user'\npassword = 'secret'\n", encoding="utf-8")
    assert "visible-user" not in repr(load_majsoul_fetch_config(valid))


def test_settings_accepts_combined_config_environment_path(tmp_path: Path, monkeypatch):
    path = tmp_path / "config.toml"
    monkeypatch.setenv("HAIUN_CONFIG", str(path))

    assert Settings().config_path == path
