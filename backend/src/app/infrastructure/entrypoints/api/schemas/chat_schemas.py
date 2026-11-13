from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field

from app.application.dto.chat_dto import AnswerQueryResponse, AnswerStatus, AnswerUsage
from app.domain.entities.conversation import Conversation
from app.domain.entities.message import Message, MessageRole
from app.domain.value_objects.source_reference import SourceReference
from app.domain.value_objects.verified_answer import VerificationConfidence


class AskQuestionRequestSchema(BaseModel):
    question: str = Field(min_length=1, max_length=2000)


class SourceReferenceSchema(BaseModel):
    """Cita documental. Los campos posteriores a `page_number` son aditivos (ADR-0014):
    un cliente que solo conoce los dos primeros sigue funcionando sin cambios."""

    document_name: str
    page_number: int | None = None
    document_title: str | None = None
    section: str | None = None
    page_end: int | None = None
    document_id: UUID | None = None
    # Enlace al PDF original servido por el backend (sin rutas del sistema de archivos).
    document_url: str | None = None

    @classmethod
    def from_value_object(cls, source: SourceReference) -> SourceReferenceSchema:
        return cls(
            document_id=source.document_id,
            document_url=f"/documents/{source.document_id}/file" if source.document_id else None,
            document_name=source.document_name,
            page_number=source.page_number,
            document_title=source.document_title,
            section=source.section,
            page_end=source.page_end,
        )


class UsageSchema(BaseModel):
    llm_calls: int
    input_tokens: int
    output_tokens: int
    cost_usd: float
    model: str | None
    simulated: bool

    @classmethod
    def from_dto(cls, usage: AnswerUsage) -> UsageSchema:
        return cls(
            llm_calls=usage.llm_calls,
            input_tokens=usage.input_tokens,
            output_tokens=usage.output_tokens,
            cost_usd=usage.cost_usd,
            model=usage.model,
            simulated=usage.simulated,
        )


class AnswerResponseSchema(BaseModel):
    message_id: UUID
    conversation_id: UUID
    answer_text: str
    status: AnswerStatus
    is_grounded: bool | None
    confidence: VerificationConfidence | None
    created_at: datetime
    sources: list[SourceReferenceSchema]
    search_query: str | None = None
    intent: str
    topic: str | None = None
    usage: UsageSchema

    @classmethod
    def from_dto(cls, dto: AnswerQueryResponse) -> AnswerResponseSchema:
        return cls(
            message_id=dto.message_id,
            conversation_id=dto.conversation_id,
            answer_text=dto.answer_text,
            status=dto.status,
            is_grounded=dto.is_grounded,
            confidence=dto.confidence,
            created_at=dto.created_at,
            sources=[SourceReferenceSchema.from_value_object(s) for s in dto.sources],
            search_query=dto.search_query,
            intent=dto.intent,
            topic=dto.topic,
            usage=UsageSchema.from_dto(dto.usage),
        )


class MessageSchema(BaseModel):
    id: UUID
    role: MessageRole
    content: str
    created_at: datetime
    is_grounded: bool | None
    confidence: VerificationConfidence | None
    sources: list[SourceReferenceSchema]
    status: str | None = None

    @classmethod
    def from_entity(cls, message: Message) -> MessageSchema:
        return cls(
            id=message.id,
            role=message.role,
            content=message.content,
            created_at=message.created_at,
            is_grounded=message.is_grounded,
            confidence=message.confidence,
            status=message.status,
            sources=(
                [SourceReferenceSchema.from_value_object(source) for source in message.sources]
                if message.sources
                else [SourceReferenceSchema(document_name=name) for name in message.source_document_names]
            ),
        )


class ConversationSchema(BaseModel):
    id: UUID
    created_at: datetime
    messages: list[MessageSchema]

    @classmethod
    def from_entity(cls, conversation: Conversation) -> ConversationSchema:
        return cls(
            id=conversation.id,
            created_at=conversation.created_at,
            messages=[MessageSchema.from_entity(m) for m in conversation.messages],
        )
