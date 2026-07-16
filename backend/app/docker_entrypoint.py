import errno
import os
import stat
import sys
import tempfile
from collections.abc import Mapping, Sequence
from pathlib import Path


APP_UID = 10001
APP_GID = 10001
DEFAULT_CONFIG = Path("/app/config/config.toml")
STAGED_CONFIG = Path("/run/haiun-config/config.toml")


class ConfigStagingError(Exception):
    def __init__(self, path: Path):
        self.path = path
        super().__init__(f"Cannot securely stage Haiun config: {path}")


def _open_regular_source(path: Path) -> int | None:
    flags = (
        os.O_RDONLY
        | getattr(os, "O_CLOEXEC", 0)
        | getattr(os, "O_NOFOLLOW", 0)
        | getattr(os, "O_NONBLOCK", 0)
    )
    try:
        descriptor = os.open(path, flags)
    except OSError as error:
        if error.errno == errno.ENOENT:
            return None
        raise ConfigStagingError(path) from None

    try:
        if not stat.S_ISREG(os.fstat(descriptor).st_mode):
            raise ConfigStagingError(path)
    except BaseException:
        os.close(descriptor)
        raise
    return descriptor


def _prepare_directory(path: Path, *, uid: int, gid: int) -> None:
    path.mkdir(mode=0o711, parents=True, exist_ok=True)
    if not stat.S_ISDIR(path.lstat().st_mode):
        raise OSError(errno.ENOTDIR, "staging path is not a directory")
    os.chown(path, uid, gid)
    os.chmod(path, 0o711)


def _copy_descriptor(source: int, destination: int) -> None:
    while chunk := os.read(source, 1024 * 1024):
        view = memoryview(chunk)
        while view:
            written = os.write(destination, view)
            view = view[written:]


def stage_config(
    source: Path,
    destination: Path = STAGED_CONFIG,
    *,
    target_uid: int = APP_UID,
    target_gid: int = APP_GID,
    directory_uid: int = 0,
    directory_gid: int = 0,
) -> bool:
    source_descriptor = _open_regular_source(source)
    if source_descriptor is None:
        return False

    temporary_path: Path | None = None
    temporary_descriptor: int | None = None
    try:
        _prepare_directory(
            destination.parent,
            uid=directory_uid,
            gid=directory_gid,
        )
        temporary_descriptor, temporary_name = tempfile.mkstemp(
            dir=destination.parent,
            prefix=".config.",
        )
        temporary_path = Path(temporary_name)
        _copy_descriptor(source_descriptor, temporary_descriptor)
        os.fchmod(temporary_descriptor, 0o400)
        os.fchown(temporary_descriptor, target_uid, target_gid)
        os.fsync(temporary_descriptor)
        os.close(temporary_descriptor)
        temporary_descriptor = None
        os.replace(temporary_path, destination)
        temporary_path = None
        return True
    except ConfigStagingError:
        raise
    except OSError:
        raise ConfigStagingError(source) from None
    finally:
        os.close(source_descriptor)
        if temporary_descriptor is not None:
            os.close(temporary_descriptor)
        if temporary_path is not None:
            try:
                temporary_path.unlink()
            except FileNotFoundError:
                pass


def drop_privileges(*, uid: int = APP_UID, gid: int = APP_GID) -> None:
    os.setgroups([])
    os.setgid(gid)
    os.setuid(uid)
    if (
        os.getgroups()
        or os.getgid() != gid
        or os.getegid() != gid
        or os.getuid() != uid
        or os.geteuid() != uid
    ):
        raise RuntimeError("Haiun failed to drop Docker bootstrap privileges")


def run(
    command: Sequence[str],
    *,
    environ: Mapping[str, str] | None = None,
) -> None:
    if not command:
        raise RuntimeError("Haiun Docker entrypoint requires a command")

    resolved_environment = dict(os.environ if environ is None else environ)
    if os.geteuid() == 0:
        source = Path(resolved_environment.get("HAIUN_CONFIG", DEFAULT_CONFIG))
        if stage_config(source):
            resolved_environment["HAIUN_CONFIG"] = str(STAGED_CONFIG)
        drop_privileges()

    os.execvpe(command[0], list(command), resolved_environment)


def main() -> int:
    try:
        run(sys.argv[1:])
    except ConfigStagingError as error:
        print(error, file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
