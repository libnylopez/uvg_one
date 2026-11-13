from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from uuid import UUID

from app.domain.value_objects.source_reference import SourceReference
from app.domain.value_objects.verified_answer import VerificationConfidence


class AnswerStatus(str, Enum):
    """Qué tipo de respuesta recibió el usuario (la interfaz la presenta distinto)."""

    ANSWERED = "answered"  # respuesta fundamentada en documentos, con fuentes
    ABSTAINED = "abstained"  # no hay evidencia suficiente: el agente lo reconoce
    SMALLTALK = "smalltalk"  # saludo, agradecimiento o presentación: sin búsqueda
    NO_DOCUMENTS = "no_documents"  # la base de conocimiento está vacía
    ERROR = "error"  # falló la API de Claude u otro servicio


@dataclass(frozen=True, slots=True)
class AnswerQueryRequest:
    user_id: UUID
    question: str


@dataclass(frozen=True, slots=True)
class AnswerQueryResponse:
    message_id: UUID
    conversation_id: UUID
    answer_text: str
    status: AnswerStatus
    is_grounded: bool | None
    confidence: VerificationConfidence | None
    created_at: datetime
    sources: tuple[SourceReference, ...] = field(default_factory=tuple)
    # Consulta que realmente se buscó (difiere de la pregunta en los seguimientos).
    search_query: str | None = None
