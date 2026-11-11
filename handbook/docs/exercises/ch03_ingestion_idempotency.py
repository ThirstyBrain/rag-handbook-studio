"""Chapter 3 exercise: idempotent, incremental ingestion with deletion propagation
and dead-letter handling (stdlib only, in-memory store).

What it demonstrates and asserts
  1. Idempotency: processing the same (tenant, source_id, content_sha256) twice
     creates exactly one document version and one set of chunks.
  2. Change detection: unchanged content is skipped; changed content creates a new
     version and retires the old version's chunks atomically (no mixed versions).
  3. Deletion propagation: a source tombstone removes all chunks of the document.
  4. Retry + dead-letter: a poison document fails N times, then lands in a DLQ with
     a reason; other documents continue to be processed.

This is a teaching model of the control flow, not a production implementation:
the real store is Postgres with transactions (see reference-implementation, M5).

Run:  python -I ch03_ingestion_idempotency.py
"""
from __future__ import annotations

import hashlib
from dataclasses import dataclass, field


def sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def normalize(text: str) -> str:
    """Minimal normalization so cosmetic differences don't create new versions."""
    return "\n".join(line.rstrip() for line in text.replace("\r\n", "\n").strip().split("\n"))


@dataclass(frozen=True)
class SourceEvent:
    tenant_id: str
    source_id: str          # stable ID in the system of record (e.g. path / URL / ID)
    kind: str               # "upsert" | "delete"
    content: str | None = None


@dataclass
class Store:
    # (tenant, source_id) -> current version info
    docs: dict[tuple[str, str], dict] = field(default_factory=dict)
    # chunk_id -> (tenant, source_id, version, text)
    chunks: dict[str, tuple[str, str, int, str]] = field(default_factory=dict)
    dlq: list[dict] = field(default_factory=list)


def chunk_ids_for(tenant: str, source: str, version: int, n: int) -> list[str]:
    return [f"{tenant}:{source}:v{version}:c{i}" for i in range(n)]


def simple_split(text: str, size: int = 40) -> list[str]:
    words = text.split()
    return [" ".join(words[i : i + size]) for i in range(0, len(words), size)] or [""]


def ingest(store: Store, ev: SourceEvent) -> str:
    key = (ev.tenant_id, ev.source_id)

    if ev.kind == "delete":
        removed = [cid for cid, (t, s, _v, _x) in store.chunks.items() if (t, s) == key]
        for cid in removed:
            del store.chunks[cid]
        store.docs.pop(key, None)
        return f"deleted({len(removed)} chunks)"

    assert ev.content is not None
    content = normalize(ev.content)
    digest = sha256(content)
    current = store.docs.get(key)

    if current and current["sha256"] == digest:
        return "skipped(unchanged)"          # idempotent no-op

    version = (current["version"] + 1) if current else 1
    parts = simple_split(content)
    new_ids = chunk_ids_for(ev.tenant_id, ev.source_id, version, len(parts))

    # Stage the new version fully, then swap. In Postgres this is one transaction.
    staged = {cid: (ev.tenant_id, ev.source_id, version, txt) for cid, txt in zip(new_ids, parts, strict=True)}
    old_ids = [cid for cid, (t, s, _v, _x) in store.chunks.items() if (t, s) == key]
    store.chunks.update(staged)
    for cid in old_ids:
        del store.chunks[cid]
    store.docs[key] = {"sha256": digest, "version": version}
    return f"indexed(v{version}, {len(parts)} chunks)"


def process_with_retry(store: Store, ev: SourceEvent, max_attempts: int, fail_on: set[str]) -> str:
    last_err = ""
    for attempt in range(1, max_attempts + 1):
        try:
            if ev.source_id in fail_on:
                raise ValueError("unparseable document")  # simulated poison message
            return ingest(store, ev)
        except Exception as exc:  # noqa: BLE001 - teaching code; real code classifies errors
            last_err = f"{type(exc).__name__}: {exc}"
    store.dlq.append({"event": ev, "reason": last_err, "attempts": max_attempts})
    return "dead-lettered"


def main() -> None:
    s = Store()
    doc = "Parental leave policy. " + "word " * 100

    # 1) Idempotency
    e1 = SourceEvent("t1", "hr/policy.md", "upsert", doc)
    assert ingest(s, e1).startswith("indexed(v1")
    n_chunks = len(s.chunks)
    assert ingest(s, e1) == "skipped(unchanged)"
    assert len(s.chunks) == n_chunks and s.docs[("t1", "hr/policy.md")]["version"] == 1
    # cosmetic change (CRLF + trailing spaces) must not create a new version
    cosmetic = SourceEvent("t1", "hr/policy.md", "upsert", doc.replace("\n", "\r\n") + "   ")
    assert ingest(s, cosmetic) == "skipped(unchanged)"
    print("1. idempotent re-ingestion + cosmetic change skipped: OK")

    # 2) Changed content -> new version, old chunks gone, never mixed
    e2 = SourceEvent("t1", "hr/policy.md", "upsert", doc + " Updated clause.")
    assert ingest(s, e2).startswith("indexed(v2")
    versions = {v for (_t, _s, v, _x) in s.chunks.values()}
    assert versions == {2}, versions
    print("2. new version replaces old atomically (versions present:", versions, "): OK")

    # 2b) revert: content goes back to an EARLIER version (A -> B -> A) and must be accepted as a new version
    assert ingest(s, e1).startswith("indexed(v3"), "a revert to earlier content must create a new version"
    assert {v for (_t, _s, v, _x) in s.chunks.values()} == {3}
    assert ingest(s, e1) == "skipped(unchanged)"        # re-sending the now-current content is still a no-op
    print("2b. revert A -> B -> A is accepted as v3; re-sending it is skipped: OK")

    # tenant isolation of keys: same source_id in another tenant is a different document
    ingest(s, SourceEvent("t2", "hr/policy.md", "upsert", "other tenant content"))
    assert {t for (t, _s, _v, _x) in s.chunks.values()} == {"t1", "t2"}

    # 3) Deletion propagation
    assert ingest(s, SourceEvent("t1", "hr/policy.md", "delete")).startswith("deleted(")
    assert all(t != "t1" for (t, _s, _v, _x) in s.chunks.values())
    assert ("t1", "hr/policy.md") not in s.docs
    assert any(t == "t2" for (t, _s, _v, _x) in s.chunks.values())  # other tenant untouched
    print("3. delete removes only that tenant's chunks: OK")

    # 4) Poison message -> DLQ, others continue
    batch = [
        SourceEvent("t1", "bad.pdf", "upsert", "x"),
        SourceEvent("t1", "ok.md", "upsert", "fine document"),
    ]
    results = [process_with_retry(s, ev, max_attempts=3, fail_on={"bad.pdf"}) for ev in batch]
    assert results[0] == "dead-lettered" and results[1].startswith("indexed")
    assert len(s.dlq) == 1 and s.dlq[0]["attempts"] == 3 and "unparseable" in s.dlq[0]["reason"]
    print("4. poison document dead-lettered after 3 attempts; batch continued: OK")

    print("\nAll assertions passed.")


if __name__ == "__main__":
    main()
