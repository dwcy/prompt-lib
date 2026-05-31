"""Unit tests for cabal.init_project_service (T069).

These tests are written ahead of the implementation. They MUST fail with
ImportError until cabal.init_project_service exists — that is the TDD red state.
"""

from __future__ import annotations

import io
import tarfile
from pathlib import Path, PurePosixPath

import pytest


def _injectable(**overrides):
    from cabal.init_project_service import InjectableFile

    defaults = dict(
        source_path=Path("/tmp/source.txt"),
        dest_relpath=PurePosixPath("README.md"),
        size_bytes=10,
    )
    defaults.update(overrides)
    return InjectableFile(**defaults)


def test_injectable_refuses_absolute_destpath():
    with pytest.raises(ValueError):
        _injectable(dest_relpath=PurePosixPath("/etc/passwd"))


def test_injectable_refuses_dotdot_segment():
    with pytest.raises(ValueError):
        _injectable(dest_relpath=PurePosixPath("../escape.txt"))

    with pytest.raises(ValueError):
        _injectable(dest_relpath=PurePosixPath("foo/../../escape.txt"))


def test_injectable_accepts_clean_relpath():
    f = _injectable(dest_relpath=PurePosixPath(".claude/agents/foo.md"))

    assert f.dest_relpath == PurePosixPath(".claude/agents/foo.md")


def _tar_with(members: list[tuple[tarfile.TarInfo, bytes | None]]) -> tarfile.TarFile:
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w:gz") as t:
        for info, data in members:
            if data is None:
                t.addfile(info)
            else:
                t.addfile(info, io.BytesIO(data))
    buf.seek(0)
    return tarfile.open(fileobj=buf, mode="r:gz")


def test_validate_safe_accepts_clean_archive(tmp_project_dir):
    from cabal.init_project_service import _validate_safe

    info = tarfile.TarInfo("proj/README.md")
    data = b"hello"
    info.size = len(data)
    tar = _tar_with([(info, data)])

    _validate_safe(tar)


def test_validate_safe_rejects_absolute_path():
    from cabal.init_project_service import UnsafeArchiveError, _validate_safe

    info = tarfile.TarInfo("/etc/passwd")
    data = b"x"
    info.size = len(data)
    tar = _tar_with([(info, data)])

    with pytest.raises(UnsafeArchiveError, match="absolute|unsafe"):
        _validate_safe(tar)


def test_validate_safe_rejects_dotdot():
    from cabal.init_project_service import UnsafeArchiveError, _validate_safe

    info = tarfile.TarInfo("proj/../escape.txt")
    data = b"x"
    info.size = len(data)
    tar = _tar_with([(info, data)])

    with pytest.raises(UnsafeArchiveError):
        _validate_safe(tar)


def test_validate_safe_rejects_symlink():
    from cabal.init_project_service import UnsafeArchiveError, _validate_safe

    info = tarfile.TarInfo("proj/link")
    info.type = tarfile.SYMTYPE
    info.linkname = "/etc/passwd"
    info.size = 0
    tar = _tar_with([(info, None)])

    with pytest.raises(UnsafeArchiveError):
        _validate_safe(tar)


def test_validate_safe_rejects_hardlink():
    from cabal.init_project_service import UnsafeArchiveError, _validate_safe

    info = tarfile.TarInfo("proj/hardlink")
    info.type = tarfile.LNKTYPE
    info.linkname = "proj/README.md"
    info.size = 0
    tar = _tar_with([(info, None)])

    with pytest.raises(UnsafeArchiveError):
        _validate_safe(tar)


def test_validate_safe_rejects_windows_drive_path():
    from cabal.init_project_service import UnsafeArchiveError, _validate_safe

    info = tarfile.TarInfo("C:\\Windows\\System32\\evil.dll")
    data = b"x"
    info.size = len(data)
    tar = _tar_with([(info, data)])

    with pytest.raises(UnsafeArchiveError):
        _validate_safe(tar)
