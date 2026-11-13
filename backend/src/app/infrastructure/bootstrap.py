"""Arranque de UVG ONE: deja el índice vectorial alineado con la carpeta documentos_uvg/."""

from __future__ import annotations

from pathlib import Path

from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession

from app.application.use_cases.sync_document_folder import SyncDocumentFolderUseCase, SyncReport
from app.domain.ports.document_text_extractor_port import DocumentTextExtractorPort
from app.domain.ports.embedding_port import EmbeddingPort
from app.domain.ports.vector_store_port import VectorStorePort
from app.infrastructure.adapters.persistence.postgres_document_repository import (
    PostgresDocumentRepository,
)
from app.infrastructure.adapters.vector_store.chroma_vector_store import ChromaVectorStoreAdapter
from app.infrastructure.config.settings import RagSettings
from app.infrastructure.rag_factory import build_indexing_pipeline, index_signature


async def sync_documents(
    session: AsyncSession,
    folder: Path,
    chroma: ChromaVectorStoreAdapter,
    text_extractor: DocumentTextExtractorPort,
    embedding_port: EmbeddingPort,
    vector_store_port: VectorStorePort,
    rag_settings: RagSettings,
) -> SyncReport:
    repository = PostgresDocumentRepository(session)

    # Si el índice se construyó con otro modelo de embeddings o fragmentación, sus vectores
    # no son comparables con los nuevos: se vacía y se reindexa todo.
    expected = index_signature(rag_settings)
    stored = chroma.read_index_signature()
    force = stored is not None and stored != expected
    if force:
        logger.warning("La configuración del índice cambió ({} → {}); se reindexa todo", stored, expected)
        chroma.reset()

    # Fragmentos de documentos que ya no están registrados (p. ej. se borró la base de datos).
    known = {document.id for document in await repository.list_all()}
    in_index = chroma.document_ids()
    for orphan in in_index - known:
        chroma.delete_by_document_id(orphan)
        logger.info("Fragmentos huérfanos eliminados del índice: documento {}", orphan)

    pipeline = build_indexing_pipeline(text_extractor, embedding_port, vector_store_port, rag_settings)
    report = await SyncDocumentFolderUseCase(repository, vector_store_port, pipeline).execute(
        folder, force=force, indexed_ids=in_index & known
    )
    await session.commit()
    chroma.write_index_signature(expected)
    return report
