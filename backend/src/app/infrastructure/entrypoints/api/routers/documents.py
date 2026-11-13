from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Annotated
from urllib.parse import quote
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import FileResponse
from pydantic import BaseModel

from app.domain.ports.document_repository_port import DocumentRepositoryPort
from app.domain.services.document_naming import title_from_filename
from app.infrastructure.adapters.persistence.database import get_session_factory
from app.infrastructure.bootstrap import sync_documents
from app.infrastructure.config.settings import get_rag_settings
from app.infrastructure.entrypoints.api.dependencies import get_document_repository

router = APIRouter(prefix="/documents", tags=["documents"])
_sync_lock = asyncio.Lock()


class DocumentSchema(BaseModel):
    document_id: UUID
    url: str
    filename: str
    title: str
    status: str
    chunk_count: int
    error_message: str | None


class KnowledgeBaseSchema(BaseModel):
    folder: str
    total_documents: int
    indexed_documents: int
    total_chunks: int
    skipped_files: list[str]
    documents: list[DocumentSchema]


@router.get("", response_model=KnowledgeBaseSchema)
async def list_documents(
    request: Request,
    repository: Annotated[DocumentRepositoryPort, Depends(get_document_repository)],
) -> KnowledgeBaseSchema:
    """Estado de la base de conocimiento: qué PDF de documentos_uvg/ están indexados."""
    state = request.app.state
    outlines = {outline.document_id: outline for outline in state.corpus_index.list_outlines()}
    chunk_counts = state.corpus_index.chunk_counts()
    documents = sorted(await repository.list_all(), key=lambda d: d.filename.casefold())
    items = [
        DocumentSchema(
            document_id=document.id,
            url=document_file_url(document.id),
            filename=document.filename,
            title=outlines[document.id].title if document.id in outlines else title_from_filename(document.filename.split("/")[-1]),
            status=document.status.value,
            chunk_count=chunk_counts.get(document.id, 0),
            error_message=document.error_message,
        )
        for document in documents
    ]
    last_sync = getattr(state, "last_sync", None)
    return KnowledgeBaseSchema(
        folder="documentos_uvg/",
        total_documents=len(items),
        indexed_documents=sum(1 for item in items if item.status == "indexed"),
        total_chunks=state.chroma.count(),
        skipped_files=list(last_sync.skipped_files) if last_sync else [],
        documents=items,
    )


class SyncOutcomeSchema(BaseModel):
    filename: str
    action: str
    chunk_count: int
    error: str | None


class SyncReportSchema(BaseModel):
    summary: str
    outcomes: list[SyncOutcomeSchema]
    skipped_files: list[str]


@router.post("/sync", response_model=SyncReportSchema)
async def sync_folder(request: Request) -> SyncReportSchema:
    """Vuelve a leer documentos_uvg/ sin reiniciar: indexa nuevos, reindexa cambiados y borra eliminados."""
    state = request.app.state
    async with _sync_lock:
        async with get_session_factory()() as session:
            report = await sync_documents(
                session,
                state.documents_dir,
                state.chroma,
                state.text_extractor_port,
                state.embedding_port,
                state.vector_store_port,
                get_rag_settings(),
            )
        state.corpus_index.reload()
        state.last_sync = report
    return SyncReportSchema(
        summary=report.summary,
        outcomes=[
            SyncOutcomeSchema(filename=o.filename, action=o.action, chunk_count=o.chunk_count, error=o.error)
            for o in report.outcomes
        ],
        skipped_files=report.skipped_files,
    )


def document_file_url(document_id: UUID) -> str:
    return f"/documents/{document_id}/file"


def resolve_document_file(root: Path, relative_name: str) -> Path | None:
    """Ruta segura de un PDF dentro de `root`; None si no existe o queda fuera de la carpeta.

    Se resuelven enlaces simbólicos y «..» antes de comparar: ningún nombre registrado puede
    apuntar fuera de documentos_uvg/.
    """
    base = root.resolve()
    candidate = (base / relative_name).resolve()
    if not candidate.is_relative_to(base) or candidate.suffix.lower() != ".pdf" or not candidate.is_file():
        return None
    return candidate


@router.api_route("/{document_id}/file", methods=["GET", "HEAD"], response_class=FileResponse)
async def document_file(
    document_id: UUID,
    request: Request,
    repository: Annotated[DocumentRepositoryPort, Depends(get_document_repository)],
) -> FileResponse:
    """PDF original para verla en el navegador (admite #page=N en visores compatibles). Solo lectura."""
    document = await repository.get_by_id(document_id)
    path = resolve_document_file(request.app.state.documents_dir, document.filename) if document else None
    if path is None:
        raise HTTPException(status_code=404, detail="Documento no encontrado")
    return FileResponse(
        path,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f"inline; filename*=UTF-8''{quote(path.name)}",
            "X-Content-Type-Options": "nosniff",
            "Cache-Control": "private, max-age=3600",
        },
    )
