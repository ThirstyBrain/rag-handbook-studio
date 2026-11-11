from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request, Response

from rag_service.core.errors import AppError
from rag_service.db.identity import Identity
from rag_service.features.ingestion.schemas import DocumentInfo, DocumentList, UploadResponse
from rag_service.features.ingestion.service import IngestionService
from rag_service.security.identity import get_identity

router = APIRouter(prefix="/v1/documents", tags=["documents"])
CurrentIdentity = Annotated[Identity, Depends(get_identity)]


def get_ingestion_service(request: Request) -> IngestionService:
    service: IngestionService | None = getattr(request.app.state, "ingestion_service", None)
    if service is None:
        raise AppError("ingestion_not_configured", "Ingestion is not configured", 503)
    return service


Service = Annotated[IngestionService, Depends(get_ingestion_service)]


@router.post("", response_model=UploadResponse, status_code=202)
async def upload(
    request: Request,
    response: Response,
    identity: CurrentIdentity,
    service: Service,
    source_id: Annotated[str, Query(min_length=1, max_length=1000)],
    title: Annotated[str, Query(max_length=500)] = "",
    acl: Annotated[list[str] | None, Query(max_length=64)] = None,
) -> UploadResponse:
    """Upload a document as the raw request body. 202 = new version queued, 200 = identical content."""
    length_header = request.headers.get("content-length")
    result = await service.ingest(
        identity,
        source_id=source_id,
        title=title,
        acl=tuple(acl) if acl else identity.groups,
        declared_type=request.headers.get("content-type"),
        declared_length=int(length_header) if length_header and length_header.isdigit() else None,
        body=request.stream(),
    )
    if result.duplicate:
        response.status_code = 200
    return result


@router.get("", response_model=DocumentList)
async def list_documents(
    identity: CurrentIdentity,
    service: Service,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    offset: Annotated[int, Query(ge=0, le=10_000)] = 0,
) -> DocumentList:
    return await service.list_documents(identity, limit, offset)


@router.get("/{document_id}", response_model=DocumentInfo)
async def get_document(
    document_id: UUID, identity: CurrentIdentity, service: Service
) -> DocumentInfo:
    return await service.get_document(identity, document_id)


@router.delete("/{document_id}", status_code=204)
async def delete_document(
    document_id: UUID, identity: CurrentIdentity, service: Service
) -> Response:
    await service.delete_document(identity, document_id)
    return Response(status_code=204)
