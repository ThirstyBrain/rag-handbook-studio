"""Raw-object storage port and a filesystem adapter (ADR-014).

Keys are *constructed*, never taken from clients: ``tenants/<tenant uuid>/<document uuid>/<sha256>``.
Every key is validated against that exact shape before it touches the filesystem, so a crafted key
cannot traverse out of the storage root. Objects are immutable and content-addressed within a document;
two documents never share an object, so deleting one document can never remove another's data.

An Azure Blob adapter implements the same port in the infrastructure component (it needs Azurite or a
real account to be tested).
"""

from __future__ import annotations

import hashlib
import os
import re
import tempfile
from pathlib import Path
from typing import BinaryIO, Protocol
from uuid import UUID

_KEY = re.compile(
    r"^tenants/[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}"
    r"/[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}/[0-9a-f]{64}$"
)
_CHUNK = 1024 * 1024


class StorageError(Exception):
    """Storage failure. Messages never include keys' content or paths."""


def raw_key(tenant_id: UUID, document_id: UUID, sha256: str) -> str:
    key = f"tenants/{tenant_id}/{document_id}/{sha256}"
    if not _KEY.fullmatch(key):
        raise StorageError("invalid object key components")
    return key


def tenant_prefix(tenant_id: UUID) -> str:
    return f"tenants/{tenant_id}/"


def validate_key(key: str) -> str:
    if not _KEY.fullmatch(key):
        raise StorageError("invalid object key")
    return key


class ObjectStore(Protocol):
    def put(self, key: str, data: BinaryIO, *, sha256: str) -> None:
        """Store ``data`` under ``key`` (idempotent). Rejects data whose hash differs from ``sha256``."""

    def exists(self, key: str) -> bool: ...

    def sha256(self, key: str) -> str:
        """Hash of the stored bytes, computed by streaming."""

    def open(self, key: str) -> BinaryIO: ...

    def delete(self, key: str) -> None:
        """Delete if present; deleting a missing object is not an error."""


class FilesystemObjectStore:
    def __init__(self, root: Path) -> None:
        self._root = root.resolve()
        self._root.mkdir(parents=True, exist_ok=True)

    def _path(self, key: str) -> Path:
        path = (self._root / validate_key(key)).resolve()
        if self._root not in path.parents:  # defence in depth on top of the key regex
            raise StorageError("object path escapes the storage root")
        return path

    def put(self, key: str, data: BinaryIO, *, sha256: str) -> None:
        path = self._path(key)
        if path.exists():
            return
        path.parent.mkdir(parents=True, exist_ok=True)
        digest = hashlib.sha256()
        fd, tmp_name = tempfile.mkstemp(dir=path.parent, prefix=".tmp-")
        try:
            with os.fdopen(fd, "wb") as out:
                while chunk := data.read(_CHUNK):
                    digest.update(chunk)
                    out.write(chunk)
            if digest.hexdigest() != sha256:
                raise StorageError("content hash does not match the declared hash")
            os.replace(tmp_name, path)  # atomic: readers never see a partial object
        finally:
            if os.path.exists(tmp_name):
                os.unlink(tmp_name)

    def exists(self, key: str) -> bool:
        return self._path(key).is_file()

    def sha256(self, key: str) -> str:
        digest = hashlib.sha256()
        with self._path(key).open("rb") as handle:
            while chunk := handle.read(_CHUNK):
                digest.update(chunk)
        return digest.hexdigest()

    def open(self, key: str) -> BinaryIO:
        return self._path(key).open("rb")

    def delete(self, key: str) -> None:
        self._path(key).unlink(missing_ok=True)
