import sqlite3
from pathlib import Path

from fastapi.testclient import TestClient

from app.auth import AdminLoginLimiter
from app.config import Settings
from app.main import create_app


ADMIN_PASSWORD = "correct-admin-password"


def write_config(path: Path, password: str = ADMIN_PASSWORD) -> None:
    path.write_text(
        "[admin]\n"
        f'password = "{password}"\n'
        "session_hours = 12\n",
        encoding="utf-8",
    )


def configured_settings(tmp_path: Path) -> Settings:
    config_path = tmp_path / "config.toml"
    write_config(config_path)
    return Settings(data_dir=tmp_path / "data", config_path=config_path)


def test_guest_role_and_unconfigured_login_stay_locked(tmp_path: Path):
    settings = Settings(data_dir=tmp_path / "data", config_path=tmp_path / "missing.toml")
    with TestClient(create_app(settings)) as client:
        assert client.get("/api/access").json() == {"role": "guest"}

        response = client.post("/api/admin/session", json={"secret": ADMIN_PASSWORD})

    assert response.status_code == 401
    assert response.json()["code"] == "ADMIN_AUTH_FAILED"
    assert ADMIN_PASSWORD not in response.text


def test_access_response_is_private_and_varies_by_cookie(tmp_path: Path):
    settings = configured_settings(tmp_path)
    with TestClient(create_app(settings)) as client:
        guest = client.get("/api/access")
        client.post("/api/admin/session", json={"secret": ADMIN_PASSWORD})
        admin = client.get("/api/access")

    assert guest.headers["cache-control"] == "private, no-store"
    assert guest.headers["vary"] == "Cookie"
    assert admin.headers["cache-control"] == "private, no-store"
    assert admin.headers["vary"] == "Cookie"


def test_admin_login_sets_session_and_logout_revokes_it(tmp_path: Path):
    settings = configured_settings(tmp_path)
    with TestClient(create_app(settings)) as client:
        failed = client.post("/api/admin/session", json={"secret": "wrong-admin-password"})
        assert failed.status_code == 401
        assert failed.json()["code"] == "ADMIN_AUTH_FAILED"

        response = client.post("/api/admin/session", json={"secret": ADMIN_PASSWORD})
        assert response.status_code == 200
        assert response.json() == {"role": "admin"}
        assert "httponly" in response.headers["set-cookie"].lower()
        assert "samesite=lax" in response.headers["set-cookie"].lower()
        assert client.get("/api/access").json() == {"role": "admin"}

        logout = client.delete("/api/admin/session")
        assert logout.status_code == 200
        assert logout.json() == {"role": "guest"}
        assert client.get("/api/access").json() == {"role": "guest"}


def test_admin_session_database_contains_only_a_token_hash(tmp_path: Path):
    settings = configured_settings(tmp_path)
    with TestClient(create_app(settings)) as client:
        response = client.post("/api/admin/session", json={"secret": ADMIN_PASSWORD})
        raw_token = response.cookies["haiun_admin_session"]

        with sqlite3.connect(settings.data_dir / "haiun.sqlite3") as connection:
            token_hash = connection.execute("SELECT token_hash FROM admin_sessions").fetchone()[0]

    assert len(token_hash) == 64
    assert token_hash != raw_token
    assert raw_token not in (settings.data_dir / "haiun.sqlite3").read_bytes().decode("latin-1")


def test_expired_admin_session_is_treated_as_guest(tmp_path: Path):
    settings = configured_settings(tmp_path)
    with TestClient(create_app(settings)) as client:
        client.post("/api/admin/session", json={"secret": ADMIN_PASSWORD})
        with sqlite3.connect(settings.data_dir / "haiun.sqlite3") as connection:
            connection.execute("UPDATE admin_sessions SET expires_at = ?", ("2000-01-01 00:00:00",))
            connection.commit()

        assert client.get("/api/access").json() == {"role": "guest"}


def test_https_admin_login_sets_secure_cookie(tmp_path: Path):
    settings = configured_settings(tmp_path)
    with TestClient(create_app(settings), base_url="https://testserver") as client:
        response = client.post("/api/admin/session", json={"secret": ADMIN_PASSWORD})

    assert "secure" in response.headers["set-cookie"].lower()


def test_admin_login_is_rate_limited_after_five_failures(tmp_path: Path):
    settings = configured_settings(tmp_path)
    with TestClient(create_app(settings)) as client:
        for _ in range(5):
            assert client.post(
                "/api/admin/session",
                json={"secret": "wrong-admin-password"},
            ).status_code == 401

        response = client.post("/api/admin/session", json={"secret": ADMIN_PASSWORD})

    assert response.status_code == 429
    assert response.json()["code"] == "ADMIN_AUTH_RATE_LIMITED"
    assert ADMIN_PASSWORD not in response.text


def test_admin_login_limiter_prunes_expired_client_keys(monkeypatch):
    now = 1000.0
    monkeypatch.setattr("app.auth.time.monotonic", lambda: now)
    limiter = AdminLoginLimiter(window_seconds=300)

    assert limiter.is_limited("unseen-client") is False
    assert "unseen-client" not in limiter._failures

    limiter.record_failure("expired-client")
    assert "expired-client" in limiter._failures

    now += 301
    assert limiter.is_limited("expired-client") is False
    assert "expired-client" not in limiter._failures
