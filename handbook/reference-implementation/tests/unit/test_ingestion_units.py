"""No database: content-type detection, object storage and its key safety, dev-identity rules."""

from __future__ import annotations

import hashlib
import io
from pathlib import Path
from uuid import uuid4

import pytest
from fastapi import FastAPI, Request
from pydantic import ValidationError

from rag_service.core.config import Settings
from rag_service.core.errors import AppError
from rag_service.features.ingestion.media import DOCX, PDF, detect_media_type
from rag_service.features.ingestion.storage import (
    FilesystemObjectStore,
    StorageError,
    raw_key,
    tenant_prefix,
    validate_key,
)
from rag_service.security.identity import get_identity

# ------------------------------------------------------------------ media detection


@pytest.mark.parametrize(
    ("head", "declared", "expected"),
    [
        (b"hello world\n", None, "text/plain"),
        (b"hello world\n", "text/plain; charset=utf-8", "text/plain"),
        (b"# Title\n", "text/markdown", "text/markdown"),
        (b"<html><body>x</body></html>", "text/html", "text/html"),
        (b"hello", "application/octet-stream", "text/plain"),
        (b"%PDF-1.7\n...", None, PDF),
        (b"%PDF-1.7\n...", PDF, PDF),
        (b"PK\x03\x04rest", DOCX, DOCX),
        ("naïve café".encode(), "text/plain", "text/plain"),
        (
            "naïve".encode()[:-1],
            "text/plain",
            "text/plain",
        ),  # head cut inside a multi-byte character
    ],
)
def test_detect_accepts_allowed_content(head: bytes, declared: str | None, expected: str) -> None:
    assert detect_media_type(head, declared) == expected


@pytest.mark.parametrize(
    ("head", "declared"),
    [
        (b"", None),
        (b"%PDF-1.7", "text/plain"),  # PDF bytes declared as text
        (b"plain text", PDF),  # text declared as PDF
        (b"PK\x03\x04rest", None),  # a zip is only admitted as a declared Word document
        (b"PK\x03\x04rest", "text/plain"),
        (b"bin\x00ary", "text/plain"),  # NUL byte
        (b"\xff\xfe\xfa\xfb", "text/plain"),  # not UTF-8
        (b"MZ\x90\x00", None),  # Windows executable
        (b"\x7fELF", None),
        (b"hello", "application/x-msdownload"),  # declared type not on the allow-list
        (b"hello", "image/png"),
    ],
)
def test_detect_rejects_mismatches_and_disallowed_content(
    head: bytes, declared: str | None
) -> None:
    assert detect_media_type(head, declared) is None


# ------------------------------------------------------------------ storage keys


def test_raw_key_shape_and_validation() -> None:
    t, d, sha = uuid4(), uuid4(), "a" * 64
    key = raw_key(t, d, sha)
    assert key == f"tenants/{t}/{d}/{sha}" and key.startswith(tenant_prefix(t))
    assert validate_key(key) == key


@pytest.mark.parametrize(
    "bad",
    [
        "../etc/passwd",
        "/etc/passwd",
        "tenants/../../x",
        f"tenants/{uuid4()}/{uuid4()}/{'a' * 63}",  # short hash
        f"tenants/{uuid4()}/{uuid4()}/{'A' * 64}",  # uppercase
        f"tenants/{uuid4()}/{uuid4()}/{'a' * 64}/../x",  # trailing path
        f"tenants/{uuid4()}/{uuid4()}/{'a' * 64}\n",
        f"tenants/{uuid4()}/{uuid4()}/{'a' * 64}.txt",
        "",
    ],
)
def test_keys_that_could_escape_or_confuse_are_rejected(bad: str) -> None:
    with pytest.raises(StorageError):
        validate_key(bad)


def test_raw_key_rejects_bad_components() -> None:
    with pytest.raises(StorageError):
        raw_key(uuid4(), uuid4(), "../../etc")
    with pytest.raises(StorageError):
        raw_key(uuid4(), uuid4(), "a" * 63)


# ------------------------------------------------------------------ filesystem store


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def test_put_get_exists_delete_roundtrip(tmp_path: Path) -> None:
    store = FilesystemObjectStore(tmp_path)
    data = b"some document bytes" * 1000
    key = raw_key(uuid4(), uuid4(), sha(data))
    assert not store.exists(key)
    store.put(key, io.BytesIO(data), sha256=sha(data))
    assert store.exists(key) and store.sha256(key) == sha(data)
    with store.open(key) as handle:
        assert handle.read() == data
    store.delete(key)
    assert not store.exists(key)
    store.delete(key)  # deleting a missing object is not an error


def test_put_is_idempotent_and_never_overwrites(tmp_path: Path) -> None:
    store = FilesystemObjectStore(tmp_path)
    data = b"original"
    key = raw_key(uuid4(), uuid4(), sha(data))
    store.put(key, io.BytesIO(data), sha256=sha(data))
    store.put(key, io.BytesIO(data), sha256=sha(data))  # second put is a no-op
    assert store.sha256(key) == sha(data)


def test_hash_mismatch_is_rejected_and_leaves_nothing_behind(tmp_path: Path) -> None:
    store = FilesystemObjectStore(tmp_path)
    key = raw_key(uuid4(), uuid4(), sha(b"claimed"))
    with pytest.raises(StorageError, match="hash"):
        store.put(key, io.BytesIO(b"actually different"), sha256=sha(b"claimed"))
    assert not store.exists(key)
    leftovers = [p for p in tmp_path.rglob("*") if p.is_file()]
    assert leftovers == [], f"temporary files must be cleaned up: {leftovers}"


def test_store_refuses_keys_outside_the_expected_shape(tmp_path: Path) -> None:
    store = FilesystemObjectStore(tmp_path)
    for bad in ("../outside", "/abs/path", "tenants/x/y/z"):
        with pytest.raises(StorageError):
            store.exists(bad)
        with pytest.raises(StorageError):
            store.delete(bad)
    assert not (tmp_path.parent / "outside").exists()


def test_tenants_are_stored_under_separate_prefixes(tmp_path: Path) -> None:
    store = FilesystemObjectStore(tmp_path)
    a, b, doc = uuid4(), uuid4(), uuid4()
    data = b"same bytes"
    for tenant in (a, b):
        store.put(raw_key(tenant, doc, sha(data)), io.BytesIO(data), sha256=sha(data))
    store.delete(raw_key(a, doc, sha(data)))
    assert not store.exists(raw_key(a, doc, sha(data))) and store.exists(raw_key(b, doc, sha(data)))


# ------------------------------------------------------------------ dev identity and settings


def test_dev_identity_flag_is_refused_in_production_settings() -> None:
    with pytest.raises(ValidationError, match="dev_identity_enabled"):
        Settings(_env_file=None, environment="production", dev_identity_enabled=True)  # type: ignore[call-arg]
    Settings(_env_file=None, environment="local", dev_identity_enabled=True)  # type: ignore[call-arg]


def _request(settings: Settings, headers: dict[str, str]) -> Request:
    app = FastAPI()
    app.state.settings = settings
    scope = {
        "type": "http",
        "app": app,
        "headers": [(k.lower().encode(), v.encode()) for k, v in headers.items()],
    }
    return Request(scope)


GOOD = {"X-Dev-Tenant": str(uuid4()), "X-Dev-User": "alice", "X-Dev-Groups": "eng,hr"}


def test_dev_identity_headers_are_ignored_unless_explicitly_enabled() -> None:
    off = Settings(_env_file=None, environment="local")  # type: ignore[call-arg]
    with pytest.raises(AppError) as info:
        get_identity(_request(off, GOOD))
    assert info.value.status_code == 401


def test_dev_identity_is_refused_in_production_even_if_validation_was_bypassed() -> None:
    forced = Settings.model_construct(environment="production", dev_identity_enabled=True)
    with pytest.raises(AppError) as info:
        get_identity(_request(forced, GOOD))
    assert info.value.status_code == 401


def test_dev_identity_parses_valid_headers_and_rejects_bad_ones() -> None:
    on = Settings(_env_file=None, environment="test", dev_identity_enabled=True)  # type: ignore[call-arg]
    ident = get_identity(_request(on, GOOD))
    assert ident.user_id == "alice" and ident.groups == ("eng", "hr")
    for bad in (
        {},
        {"X-Dev-Tenant": GOOD["X-Dev-Tenant"]},
        {**GOOD, "X-Dev-Tenant": "not-a-uuid"},
        {**GOOD, "X-Dev-User": "a b"},
        {**GOOD, "X-Dev-Groups": "ok,bad group"},
    ):
        with pytest.raises(AppError) as info:
            get_identity(_request(on, bad))
        assert info.value.status_code == 401
