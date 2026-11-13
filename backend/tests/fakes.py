"""Dobles de prueba en memoria para los puertos del dominio."""

from __future__ import annotations

from collections.abc import Collection, Sequence
from pathlib import Path
from typing import Any
from uuid import UUID

from app.application.services.context_retrieval import RetrievedContext
from app.domain.entities.chunk import Chunk, RetrievedChunk
from app.domain.entities.conversation import Conversation
from app.domain.entities.document import Document, DocumentStatus
from app.domain.entities.message import Message
from app.domain.ports.conversation_repository_port import ConversationRepositoryPort
from app.domain.ports.document_indexer_port import DocumentIndexerPort
from app.domain.ports.document_repository_port import DocumentRepositoryPort
from app.domain.ports.llm_port import LLMPort
from app.domain.ports.vector_store_port import VectorStorePort
from app.domain.services.query_analyzer import QueryAnalyzer
from app.domain.value_objects.document_facts import DocumentFacts
from app.domain.value_objects.llm_completion import LLMCompletion
from app.domain.value_objects.section_anchor import SectionAnchor
from app.domain.value_objects.similarity_score import SimilarityScore
from app.shared.kernel.clock import utc_now
from app.shared.kernel.ids import new_id


class InMemoryDocumentRepository(DocumentRepositoryPort):
    def __init__(self) -> None:
        self.documents: dict[UUID, Document] = {}

    async def add(self, document: Document) -> None:
        self.documents[document.id] = document

    async def update_status(self, document_id: UUID, status: DocumentStatus, error_message: str | None = None) -> None:
        document = self.documents[document_id]
        document.status = status
        document.error_message = error_message

    async def update_source(self, document_id: UUID, storage_path: str, content_hash: str) -> None:
        self.documents[document_id].storage_path = storage_path
        self.documents[document_id].content_hash = content_hash

    async def get_by_id(self, document_id: UUID) -> Document | None:
        return self.documents.get(document_id)

    async def list_all(self) -> list[Document]:
        return list(self.documents.values())

    async def delete(self, document_id: UUID) -> None:
        self.documents.pop(document_id, None)


class InMemoryConversationRepository(ConversationRepositoryPort):
    def __init__(self) -> None:
        self.conversations: dict[UUID, Conversation] = {}

    async def get_or_create_active_conversation(self, user_id: UUID) -> Conversation:
        for conversation in self.conversations.values():
            if conversation.user_id == user_id:
                return Conversation(conversation.id, user_id, conversation.created_at, [])
        conversation = Conversation(new_id(), user_id, utc_now(), [])
        self.conversations[conversation.id] = conversation
        return Conversation(conversation.id, user_id, conversation.created_at, [])

    async def add_message(self, conversation_id: UUID, message: Message) -> None:
        self.conversations[conversation_id].messages.append(message)

    async def get_history(self, user_id: UUID) -> list[Conversation]:
        return [
            Conversation(c.id, c.user_id, c.created_at, list(c.messages))
            for c in self.conversations.values()
            if c.user_id == user_id
        ]


class RecordingVectorStore(VectorStorePort):
    def __init__(self) -> None:
        self.deleted: list[UUID] = []

    def upsert_chunks(self, chunks: Sequence[Chunk]) -> None:  # pragma: no cover - no usado
        pass

    def search(self, query_embedding, top_k: int, document_ids: Collection[UUID] | None = None) -> list[RetrievedChunk]:
        return []  # pragma: no cover

    def delete_by_document_id(self, document_id: UUID) -> None:
        self.deleted.append(document_id)


class FakePipeline(DocumentIndexerPort):
    """Devuelve 3 fragmentos por PDF; falla si el nombre contiene «escaneado»."""

    def __init__(self) -> None:
        self.processed: list[str] = []

    async def process(self, document_id: UUID, file_path: Path, display_name: str | None = None) -> list[Chunk]:
        self.processed.append(file_path.name)
        if "escaneado" in file_path.name:
            return []
        return [Chunk(id=new_id(), document_id=document_id, text=f"texto {i}", position=i) for i in range(3)]


class ScriptedLLM(LLMPort):
    """Devuelve respuestas predefinidas por nombre de esquema y registra cada llamada."""

    def __init__(self, responses: dict[str, Any] | None = None, error: Exception | None = None) -> None:
        self.responses = responses or {}
        self.error = error
        self.calls: list[dict[str, Any]] = []

    async def complete(self, system_prompt, user_prompt, output_schema, output_schema_name, max_tokens=None) -> LLMCompletion:
        self.calls.append({"schema": output_schema_name, "user_prompt": user_prompt})
        if self.error:
            raise self.error
        return LLMCompletion(
            content=self.responses[output_schema_name], input_tokens=1000, output_tokens=200, model="fake",
            cost_usd=0.0002,
        )


def make_passage(
    document_id: UUID, text: str, title: str = "Proceso de Admisión", page: int = 2, page_count: int | None = 3
) -> RetrievedChunk:
    return RetrievedChunk(
        chunk=Chunk(
            id=new_id(),
            document_id=document_id,
            text=text,
            position=0,
            anchor=SectionAnchor(section="Requisitos", page_start=page, page_end=page),
            document=DocumentFacts(title=title, page_count=page_count),
        ),
        score=SimilarityScore(0.8),
    )


class FixedRetrieval:
    """Sustituye a ContextRetrieval: devuelve siempre los mismos pasajes y registra las consultas."""

    def __init__(self, passages: list[RetrievedChunk]) -> None:
        self.passages = passages
        self.queries: list[str] = []
        self.originals: list[Chunk] = []

    def origin_chunks(self, chunk_ids):
        return list(self.originals)

    async def retrieve(self, query: str, topic: str | None = None) -> RetrievedContext:
        self.queries.append(query)
        return RetrievedContext(QueryAnalyzer.analyze(query), list(self.passages), list(self.passages), False)
