from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class UploadResponse(BaseModel):
    document_id: UUID
    version: int
    state: str
    duplicate: bool
    job_id: UUID | None
    media_type: str
    size_bytes: int


class VersionInfo(BaseModel):
    version: int
    state: str
    content_sha256: str
    job_state: str | None = None
    job_attempts: int | None = None


class DocumentInfo(BaseModel):
    document_id: UUID
    source_id: str
    title: str
    status: str
    created_at: datetime
    versions: list[VersionInfo]


class DocumentSummary(BaseModel):
    document_id: UUID
    source_id: str
    title: str
    status: str
    created_at: datetime


class DocumentList(BaseModel):
    items: list[DocumentSummary]
    limit: int
    offset: int
