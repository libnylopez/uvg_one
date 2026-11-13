from __future__ import annotations

from abc import ABC, abstractmethod
from uuid import UUID

from app.domain.entities.document import Document, DocumentStatus


class DocumentRepositoryPort(ABC):
    """Metadatos y estado de indexación de los documentos de documentos_uvg/."""

    @abstractmethod
    async def add(self, document: Document) -> None: ...

    @abstractmethod
    async def update_status(
        self, document_id: UUID, status: DocumentStatus, error_message: str | None = None
    ) -> None: ...

    @abstractmethod
    async def update_source(self, document_id: UUID, storage_path: str, content_hash: str) -> None:
        """Actualiza la ruta y la huella del archivo tras reindexarlo."""

    @abstractmethod
    async def get_by_id(self, document_id: UUID) -> Document | None: ...

    @abstractmethod
    async def list_all(self) -> list[Document]: ...

    @abstractmethod
    async def delete(self, document_id: UUID) -> None: ...
