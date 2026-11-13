"""Sincroniza el índice con la carpeta documentos_uvg/.

- PDF nuevo        → se extrae, fragmenta, embebe e indexa.
- PDF modificado   → se detecta por su huella SHA-256 y se reindexa.
- PDF eliminado    → sus fragmentos y su registro se borran.
- PDF sin cambios  → no se toca (un arranque normal tarda segundos).

Un PDF que falla (por ejemplo, escaneado sin texto) queda marcado con error y no detiene
la sincronización del resto.
"""

from __future__ import annotations

import asyncio
import hashlib
from dataclasses import dataclass, field
from pathlib import Path
from uuid import UUID

from loguru import logger

from app.domain.entities.document import Document, DocumentStatus
from app.domain.ports.document_indexer_port import DocumentIndexerPort
from app.domain.ports.document_repository_port import DocumentRepositoryPort
from app.domain.ports.vector_store_port import VectorStorePort
from app.shared.kernel.clock import utc_now
from app.shared.kernel.ids import new_id

SUPPORTED_SUFFIXES = frozenset({".pdf"})


@dataclass(slots=True)
class DocumentOutcome:
    filename: str
    action: str  # "indexed" | "reindexed" | "unchanged" | "removed" | "error"
    chunk_count: int = 0
    error: str | None = None


@dataclass(slots=True)
class SyncReport:
    folder: str
    outcomes: list[DocumentOutcome] = field(default_factory=list)
    skipped_files: list[str] = field(default_factory=list)

    def count(self, action: str) -> int:
        return sum(1 for outcome in self.outcomes if outcome.action == action)

    @property
    def summary(self) -> str:
        return (
            f"{self.count('indexed')} nuevos, {self.count('reindexed')} reindexados, "
            f"{self.count('unchanged')} sin cambios, {self.count('removed')} eliminados, "
            f"{self.count('error')} con error, {len(self.skipped_files)} archivos no PDF ignorados"
        )


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def scan_folder(folder: Path) -> tuple[list[Path], list[str]]:
    """PDF de la carpeta (incluidas subcarpetas) y archivos ignorados, sin ocultos."""
    pdfs: list[Path] = []
    skipped: list[str] = []
    if not folder.is_dir():
        return pdfs, skipped
    for path in sorted(folder.rglob("*")):
        relative = path.relative_to(folder)
        if not path.is_file() or any(part.startswith((".", "~$")) for part in relative.parts):
            continue
        if path.suffix.lower() in SUPPORTED_SUFFIXES:
            pdfs.append(path)
        else:
            skipped.append(relative.as_posix())
    return pdfs, skipped


class SyncDocumentFolderUseCase:
    def __init__(
        self,
        document_repository: DocumentRepositoryPort,
        vector_store: VectorStorePort,
        indexing_pipeline: DocumentIndexerPort,
    ) -> None:
        self._repository = document_repository
        self._vector_store = vector_store
        self._pipeline = indexing_pipeline

    async def execute(
        self, folder: Path, force: bool = False, indexed_ids: set[UUID] | None = None
    ) -> SyncReport:
        """`force=True` reindexa todo (p. ej. tras cambiar el modelo de embeddings).

        `indexed_ids` son los documentos que realmente tienen fragmentos en el índice
        vectorial: uno registrado como indexado pero ausente del índice (p. ej. se borró
        el volumen de ChromaDB y no la base de datos) se vuelve a indexar.
        """
        report = SyncReport(folder=str(folder))
        pdfs, report.skipped_files = scan_folder(folder)
        if not folder.is_dir():
            logger.warning("La carpeta de documentos no existe: {}", folder)

        existing = {document.filename: document for document in await self._repository.list_all()}
        for path in pdfs:
            relative = path.relative_to(folder).as_posix()
            content_hash = await asyncio.to_thread(file_sha256, path)
            document = existing.pop(relative, None)
            if document is None:
                report.outcomes.append(await self._index_new(relative, path, content_hash))
            elif (
                not force
                and document.content_hash == content_hash
                and document.status is DocumentStatus.INDEXED
                and (indexed_ids is None or document.id in indexed_ids)
            ):
                report.outcomes.append(DocumentOutcome(relative, "unchanged"))
            else:
                report.outcomes.append(await self._reindex(document, path, content_hash))

        for document in existing.values():
            await asyncio.to_thread(self._vector_store.delete_by_document_id, document.id)
            await self._repository.delete(document.id)
            logger.info("Documento eliminado del índice (ya no está en la carpeta): {}", document.filename)
            report.outcomes.append(DocumentOutcome(document.filename, "removed"))

        logger.info("Sincronización de {}: {}", folder, report.summary)
        return report

    async def _index_new(self, relative: str, path: Path, content_hash: str) -> DocumentOutcome:
        document = Document(
            id=new_id(),
            filename=relative,
            status=DocumentStatus.PENDING,
            uploaded_at=utc_now(),
            storage_path=str(path),
            content_hash=content_hash,
        )
        await self._repository.add(document)
        return await self._process(document, path, action="indexed")

    async def _reindex(self, document: Document, path: Path, content_hash: str) -> DocumentOutcome:
        await asyncio.to_thread(self._vector_store.delete_by_document_id, document.id)
        await self._repository.update_source(document.id, str(path), content_hash)
        return await self._process(document, path, action="reindexed")

    async def _process(self, document: Document, path: Path, action: str) -> DocumentOutcome:
        try:
            chunks = await self._pipeline.process(document.id, path, display_name=path.name)
            if not chunks:
                raise ValueError("no se extrajo texto (¿PDF escaneado o vacío?)")
        except Exception as error:  # noqa: BLE001 - un PDF defectuoso no debe detener el resto
            message = str(error) or type(error).__name__
            await asyncio.to_thread(self._vector_store.delete_by_document_id, document.id)
            await self._repository.update_status(document.id, DocumentStatus.ERROR, error_message=message)
            logger.error("No se pudo indexar {}: {}", document.filename, message)
            return DocumentOutcome(document.filename, "error", error=message)

        await self._repository.update_status(document.id, DocumentStatus.INDEXED)
        logger.info("{}: {} ({} fragmentos)", action, document.filename, len(chunks))
        return DocumentOutcome(document.filename, action, chunk_count=len(chunks))
