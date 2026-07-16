import os
import signal
import stat
from pathlib import Path
from time import monotonic

import pytest
from fastapi.testclient import TestClient

from app import docker_entrypoint
from app.config import Settings
from app.docker_entrypoint import ConfigStagingError, drop_privileges, stage_config
from app.main import create_app


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]


def test_docker_build_proxy_is_optional_and_environment_configured():
    dockerfile = (REPOSITORY_ROOT / "Dockerfile").read_text(encoding="utf-8")
    simple = (REPOSITORY_ROOT / "compose.simple.yml").read_text(encoding="utf-8")
    production = (REPOSITORY_ROOT / "compose.production.yml").read_text(
        encoding="utf-8"
    )
    environment_example = (REPOSITORY_ROOT / ".env.docker.example").read_text(
        encoding="utf-8"
    )

    assert "ARG HTTP_PROXY=" not in dockerfile
    assert "ARG HTTPS_PROXY=" not in dockerfile
    assert "127.0.0.1:7890" not in dockerfile
    for compose in (simple, production):
        assert "network: ${HAIUN_BUILD_NETWORK:-default}" in compose
        assert 'HTTP_PROXY: "${HAIUN_HTTP_PROXY:-}"' in compose
        assert 'HTTPS_PROXY: "${HAIUN_HTTPS_PROXY:-}"' in compose
        assert "http://127.0.0.1:7890" not in compose

    assert "HAIUN_BUILD_NETWORK=default" in environment_example
    assert "HAIUN_HTTP_PROXY=\n" in environment_example
    assert "HAIUN_HTTPS_PROXY=\n" in environment_example


def test_docker_root_execution_paths_are_absolute_and_immutable_by_design():
    dockerfile = (REPOSITORY_ROOT / "Dockerfile").read_text(encoding="utf-8")
    simple = (REPOSITORY_ROOT / "compose.simple.yml").read_text(encoding="utf-8")
    production = (REPOSITORY_ROOT / "compose.production.yml").read_text(
        encoding="utf-8"
    )

    assert "chown -R haiun:haiun /data /app" not in dockerfile
    assert 'ENTRYPOINT ["/usr/local/bin/python", "-I", ' in dockerfile
    assert '"/app/backend/app/docker_entrypoint.py"]' in dockerfile
    assert 'CMD ["/usr/local/bin/python", "-I", "-c",' in dockerfile
    for compose in (simple, production):
        assert "      - /usr/local/bin/python\n      - -I\n" in compose
        assert "      - /app/backend/app/docker_entrypoint.py\n" in compose
        assert "        - /usr/local/bin/python\n        - -I\n" in compose


def test_entrypoint_child_environment_is_consumed_by_application(tmp_path: Path, monkeypatch):
    source = tmp_path / "host-config.toml"
    staged = tmp_path / "run" / "config.toml"
    staged.parent.mkdir()
    staged.write_text(
        "[admin]\n"
        'password = "synthetic-test-password"\n'
        "session_hours = 29\n",
        encoding="utf-8",
    )
    captured: dict[str, object] = {}

    class Executed(Exception):
        pass

    def fake_stage(path: Path) -> bool:
        captured["source"] = path
        return True

    def fake_exec(file: str, command: list[str], environment: dict[str, str]) -> None:
        captured["file"] = file
        captured["command"] = command
        captured["environment"] = environment
        raise Executed

    monkeypatch.setattr(docker_entrypoint, "STAGED_CONFIG", staged)
    monkeypatch.setattr(docker_entrypoint, "stage_config", fake_stage)
    monkeypatch.setattr(docker_entrypoint, "drop_privileges", lambda: None)
    monkeypatch.setattr(docker_entrypoint.os, "geteuid", lambda: 0)
    monkeypatch.setattr(docker_entrypoint.os, "execvpe", fake_exec)

    command = ["/app/.venv/bin/python", "-m", "uvicorn"]
    with pytest.raises(Executed):
        docker_entrypoint.run(
            command,
            environ={"HAIUN_CONFIG": str(source)},
        )

    child_environment = captured["environment"]
    assert isinstance(child_environment, dict)
    assert captured["source"] == source
    assert captured["file"] == command[0]
    assert captured["command"] == command
    assert child_environment["HAIUN_CONFIG"] == str(staged)

    monkeypatch.setenv("HAIUN_CONFIG", child_environment["HAIUN_CONFIG"])
    settings = Settings(data_dir=tmp_path / "data")
    with TestClient(create_app(settings)) as client:
        assert client.app.state.settings.config_path == staged
        assert client.app.state.file_config.admin is not None
        assert client.app.state.file_config.admin.session_hours == 29


def test_stages_host_owned_private_config_without_modifying_source(tmp_path: Path):
    source = tmp_path / "host-config.toml"
    source.write_text("[admin]\nsession_hours = 19\n", encoding="utf-8")
    source.chmod(0o600)
    source_before = source.stat()
    destination = tmp_path / "run" / "config.toml"

    assert source_before.st_uid != 10001
    assert stat.S_IMODE(source_before.st_mode) == 0o600
    assert source_before.st_mode & (stat.S_IRGRP | stat.S_IROTH) == 0

    assert stage_config(
        source,
        destination,
        target_uid=os.getuid(),
        target_gid=os.getgid(),
        directory_uid=os.getuid(),
        directory_gid=os.getgid(),
    )

    source_after = source.stat()
    staged = destination.stat()
    assert source_after.st_uid == source_before.st_uid
    assert source_after.st_gid == source_before.st_gid
    assert stat.S_IMODE(source_after.st_mode) == 0o600
    assert destination.read_bytes() == source.read_bytes()
    assert (staged.st_uid, staged.st_gid) == (os.getuid(), os.getgid())
    assert stat.S_IMODE(staged.st_mode) == 0o400
    assert stat.S_IMODE(destination.parent.stat().st_mode) == 0o711


def test_missing_config_remains_allowed(tmp_path: Path):
    source = tmp_path / "missing.toml"
    destination = tmp_path / "run" / "config.toml"

    assert not stage_config(
        source,
        destination,
        target_uid=os.getuid(),
        target_gid=os.getgid(),
        directory_uid=os.getuid(),
        directory_gid=os.getgid(),
    )
    assert not destination.exists()


def test_unreadable_config_source_has_path_only_error(tmp_path: Path):
    if os.geteuid() == 0:
        pytest.skip("mode 000 is readable by root")
    source = tmp_path / "config.toml"
    source.write_text("secret-content-must-not-escape\n", encoding="utf-8")
    source.chmod(0)

    try:
        with pytest.raises(ConfigStagingError) as error:
            stage_config(
                source,
                tmp_path / "run" / "config.toml",
                target_uid=os.getuid(),
                target_gid=os.getgid(),
                directory_uid=os.getuid(),
                directory_gid=os.getgid(),
            )
    finally:
        source.chmod(0o600)

    assert str(error.value) == f"Cannot securely stage Haiun config: {source}"
    assert "secret-content-must-not-escape" not in str(error.value)


@pytest.mark.parametrize("source_kind", ["symlink", "directory"])
def test_rejects_non_regular_config_sources(tmp_path: Path, source_kind: str):
    source = tmp_path / "config.toml"
    if source_kind == "symlink":
        target = tmp_path / "target.toml"
        target.write_text("marker = true\n", encoding="utf-8")
        source.symlink_to(target)
    else:
        source.mkdir()

    with pytest.raises(ConfigStagingError) as error:
        stage_config(
            source,
            tmp_path / "run" / "config.toml",
            target_uid=os.getuid(),
            target_gid=os.getgid(),
            directory_uid=os.getuid(),
            directory_gid=os.getgid(),
        )

    assert error.value.path == source
    assert str(error.value) == f"Cannot securely stage Haiun config: {source}"


def test_replaces_previous_staged_copy_safely_on_restart(tmp_path: Path):
    source = tmp_path / "config.toml"
    destination = tmp_path / "run" / "config.toml"
    source.write_text("marker = 1\n", encoding="utf-8")

    kwargs = {
        "target_uid": os.getuid(),
        "target_gid": os.getgid(),
        "directory_uid": os.getuid(),
        "directory_gid": os.getgid(),
    }
    assert stage_config(source, destination, **kwargs)
    source.write_text("marker = 2\n", encoding="utf-8")
    assert stage_config(source, destination, **kwargs)

    assert destination.read_text(encoding="utf-8") == "marker = 2\n"
    assert stat.S_IMODE(destination.stat().st_mode) == 0o400


def test_rejects_fifo_source_without_waiting_for_a_writer(tmp_path: Path):
    source = tmp_path / "config.toml"
    os.mkfifo(source)

    def fail_if_blocked(_signum, _frame):
        raise TimeoutError("opening the config FIFO blocked")

    previous_handler = signal.signal(signal.SIGALRM, fail_if_blocked)
    signal.alarm(1)
    started_at = monotonic()
    try:
        with pytest.raises(ConfigStagingError):
            stage_config(
                source,
                tmp_path / "run" / "config.toml",
                target_uid=os.getuid(),
                target_gid=os.getgid(),
                directory_uid=os.getuid(),
                directory_gid=os.getgid(),
            )
    finally:
        signal.alarm(0)
        signal.signal(signal.SIGALRM, previous_handler)
    assert monotonic() - started_at < 0.5


@pytest.mark.parametrize("failing_operation", ["read", "write", "replace"])
def test_copy_failures_have_path_only_error_and_remove_temporary_files(
    tmp_path: Path,
    monkeypatch,
    failing_operation: str,
):
    source = tmp_path / "config.toml"
    source.write_text("secret-content-must-not-escape\n", encoding="utf-8")
    destination = tmp_path / "run" / "config.toml"

    def fail(*_args, **_kwargs):
        raise OSError("synthetic copy failure with secret-content-must-not-escape")

    monkeypatch.setattr(docker_entrypoint.os, failing_operation, fail)

    with pytest.raises(ConfigStagingError) as error:
        stage_config(
            source,
            destination,
            target_uid=os.getuid(),
            target_gid=os.getgid(),
            directory_uid=os.getuid(),
            directory_gid=os.getgid(),
        )

    assert str(error.value) == f"Cannot securely stage Haiun config: {source}"
    assert "secret-content-must-not-escape" not in str(error.value)
    assert not destination.exists()
    assert not list(destination.parent.glob(".config.*"))


def test_main_reports_one_path_only_line_without_traceback(tmp_path: Path, monkeypatch, capsys):
    source = tmp_path / "config.toml"
    source.write_text("secret-content-must-not-escape\n", encoding="utf-8")

    def fail_run(_command):
        raise ConfigStagingError(source)

    monkeypatch.setattr(docker_entrypoint, "run", fail_run)
    monkeypatch.setattr(docker_entrypoint.sys, "argv", ["docker_entrypoint.py", "command"])

    assert docker_entrypoint.main() == 1
    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err == f"Cannot securely stage Haiun config: {source}\n"
    assert "Traceback" not in captured.err
    assert "secret-content-must-not-escape" not in captured.err


def test_clears_supplementary_groups_before_dropping_gid_and_uid(monkeypatch):
    calls: list[tuple[str, object]] = []
    monkeypatch.setattr(os, "setgroups", lambda groups: calls.append(("groups", groups)))
    monkeypatch.setattr(os, "setgid", lambda gid: calls.append(("gid", gid)))
    monkeypatch.setattr(os, "setuid", lambda uid: calls.append(("uid", uid)))
    monkeypatch.setattr(os, "getgroups", lambda: [])
    monkeypatch.setattr(os, "getgid", lambda: 10001)
    monkeypatch.setattr(os, "getegid", lambda: 10001)
    monkeypatch.setattr(os, "getuid", lambda: 10001)
    monkeypatch.setattr(os, "geteuid", lambda: 10001)

    drop_privileges(uid=10001, gid=10001)

    assert calls == [("groups", []), ("gid", 10001), ("uid", 10001)]
