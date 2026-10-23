"""Private immutable filesystem byte adapter for disposable/local integration.

This adapter is NOT a Supabase Storage adapter, not a production vault ledger,
and must not be exposed through HTTP. Use a dedicated private directory.
Only VaultCoordinator may publish verification after exact read-back.
"""

from __future__ import annotations

import os
import re
import stat
from dataclasses import dataclass
from pathlib import Path

from apps.api.evidence_vault_protocol import MAX_REFERENCE_BYTES, VaultUnavailable

_KEY = re.compile(
    r"org/[0-9a-f]{32}/case/[0-9a-f]{32}/sources/[0-9a-f]{32}\Z"
)


class PrivateObjectConflict(VaultUnavailable):
    """An immutable object key already exists."""


@dataclass(frozen=True, slots=True)
class PrivateFilesystemByteStore:
    root: Path

    def __post_init__(self) -> None:
        if not isinstance(self.root, Path) or not self.root.is_absolute():
            raise ValueError("absolute private storage root required")
        if self.root.is_symlink():
            raise ValueError("storage root must not be a symlink")
        self.root.mkdir(mode=0o700, parents=True, exist_ok=True)
        if not self.root.is_dir() or self.root.is_symlink():
            raise ValueError("private storage root must be a directory")
        os.chmod(self.root, 0o700)

    def _parent_and_name(self, key: str) -> tuple[int, str]:
        if not isinstance(key, str) or not _KEY.fullmatch(key):
            raise ValueError("invalid scoped object key")
        segments = key.split("/")
        fd = os.open(self.root, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
        try:
            for segment in segments[:-1]:
                try:
                    os.mkdir(segment, mode=0o700, dir_fd=fd)
                except FileExistsError:
                    pass
                child = os.open(
                    segment, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=fd
                )
                os.close(fd)
                fd = child
            return fd, segments[-1]
        except BaseException:
            os.close(fd)
            raise

    def put_once(self, key: str, data: bytes) -> None:
        if type(data) is not bytes or not 0 < len(data) <= MAX_REFERENCE_BYTES:
            raise ValueError("bounded immutable bytes required")
        fd, name = self._parent_and_name(key)
        try:
            try:
                obj = os.open(
                    name, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW,
                    0o600, dir_fd=fd,
                )
            except FileExistsError:
                raise PrivateObjectConflict("object already exists") from None
            try:
                with os.fdopen(obj, "wb", closefd=True) as stream:
                    stream.write(data)
                    stream.flush()
                    os.fsync(stream.fileno())
                os.fsync(fd)
            except BaseException:
                # A partial object is NOT safe to overwrite or blindly retry.
                # Reconciliation must inspect the frozen key and verify bytes.
                raise
        finally:
            os.close(fd)

    def read_exact(self, key: str) -> bytes | None:
        fd, name = self._parent_and_name(key)
        try:
            try:
                obj = os.open(name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=fd)
            except FileNotFoundError:
                return None
            with os.fdopen(obj, "rb", closefd=True) as stream:
                metadata = os.fstat(stream.fileno())
                if not stat.S_ISREG(metadata.st_mode) or metadata.st_size > MAX_REFERENCE_BYTES:
                    raise VaultUnavailable("untrusted object type or size")
                data = stream.read(MAX_REFERENCE_BYTES + 1)
                if len(data) > MAX_REFERENCE_BYTES:
                    raise VaultUnavailable("object exceeded bounded read")
                return data
        finally:
            os.close(fd)
