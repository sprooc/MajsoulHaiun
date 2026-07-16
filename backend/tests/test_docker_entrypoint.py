import os
import signal
import stat
from time import monotonic
from pathlib import Path

import pytest

from app.docker_entrypoint import ConfigStagingError, drop_privileges, stage_config


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
