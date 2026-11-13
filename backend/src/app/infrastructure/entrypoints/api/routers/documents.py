from __future__ import annotations

import asyncio
from typing import Annotated

from fastapi import APIRouter, Depends, Request
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
        folder=str(state.documents_dir),
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
