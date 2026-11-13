"""Caso de uso principal de UVG ONE: responder una pregunta con RAG.

Flujo por mensaje:
  1. Saneamiento de la pregunta y lectura del historial de la conversación.
  2. Saludos y presentaciones se responden sin buscar ni llamar al modelo.
  3. Si hay historial, Claude reescribe la pregunta como consulta autosuficiente.
  4. Recuperación híbrida (semántica + léxica) y ensamblado del contexto.
  5. Sin evidencia suficiente → abstención, sin llamar al modelo.
  6. Claude responde y autoverifica en una sola llamada con salida estructurada.
  7. Respuesta no fundamentada → abstención. Fundamentada → respuesta + fuentes citadas.
"""

from __future__ import annotations

import re
import time
from collections.abc import Sequence
from datetime import datetime, timedelta, timezone
from uuid import UUID

from loguru import logger

from app.application.dto.chat_dto import AnswerQueryRequest, AnswerQueryResponse, AnswerStatus
from app.application.services.context_retrieval import ContextRetrieval
from app.application.services.query_rewriter import QueryRewriter, format_history
from app.domain.entities.chunk import RetrievedChunk
from app.domain.entities.message import Message, MessageRole
from app.domain.ports.conversation_repository_port import ConversationRepositoryPort
from app.domain.ports.document_repository_port import DocumentRepositoryPort
from app.domain.ports.verification_strategy_port import VerificationStrategyPort
from app.domain.services.message_sanitizer import MessageSanitizer
from app.domain.services.spanish_text import fold
from app.domain.value_objects.source_reference import SourceReference
from app.domain.value_objects.verified_answer import AnswerCoverage, VerificationConfidence, VerifiedAnswer
from app.shared.exceptions.domain_errors import (
    LLMGenerationError,
    LLMNotConfiguredError,
    LLMUnavailableError,
    VerificationFailedError,
)
from app.shared.kernel.clock import utc_now
from app.shared.kernel.ids import new_id

NO_EVIDENCE_MESSAGE = (
    "No encontré información sobre eso en los documentos oficiales que tengo disponibles.\n\n"
    "Puede que el tema no esté cubierto, o que con otras palabras sí lo encuentre. Intenta ser más "
    "específico, por ejemplo: «requisitos de admisión para primer ingreso» o «fechas de inicio de clases»."
)
NOT_GROUNDED_MESSAGE = (
    "Encontré documentos relacionados con tu pregunta, pero no dicen lo suficiente como para "
    "responderte con seguridad, y prefiero no darte un dato que no pueda respaldar."
)
NO_DOCUMENTS_MESSAGE = (
    "Todavía no hay documentos institucionales cargados en UVG ONE, así que no puedo responder "
    "consultas por ahora. Agrega los PDF a la carpeta `documentos_uvg/` y vuelve a intentarlo."
)
NOT_CONFIGURED_MESSAGE = (
    "El servicio de inteligencia artificial no está configurado todavía (falta o es inválida la API key "
    "de Anthropic en el archivo `.env`). La búsqueda en documentos funciona, pero no puedo redactar la respuesta."
)
UNAVAILABLE_MESSAGE = (
    "El servicio de inteligencia artificial no está disponible en este momento. "
    "Espera unos segundos y vuelve a intentarlo."
)
GENERATION_FAILED_MESSAGE = (
    "Tuve un problema al preparar la respuesta. Vuelve a intentarlo; si el problema continúa, "
    "reformula la pregunta."
)

_GREETING = re.compile(
    r"^(?:hola|holi|hey|buenas|buenos dias|buen dia|buenas tardes|buenas noches|saludos|que tal)"
    r"(?:\s+(?:uvg one|uvg|a todos|como estas|que tal))?[\s!.?¡¿,]*$"
)
_THANKS = re.compile(r"^(?:muchas\s+)?gracias(?:\s+(?:por todo|por la ayuda|uvg one))?[\s!.,]*$|^(?:ok|vale|perfecto|listo)[\s!.,]*(?:gracias)?[\s!.,]*$")
_IDENTITY = re.compile(
    r"^(?:quien eres|que eres|que puedes hacer|en que me puedes ayudar|como funcionas|"
    r"que sabes hacer|para que sirves|ayuda)[\s?!.¿¡]*$"
)
_FAREWELL = re.compile(r"^(?:adios|hasta luego|nos vemos|bye|chao)[\s!.,]*$")

_GUATEMALA = timezone(timedelta(hours=-6))
_MONTHS = ("enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto",
           "septiembre", "octubre", "noviembre", "diciembre")


def _today_in_guatemala(now: datetime | None = None) -> str:
    today = (now or datetime.now(_GUATEMALA)).astimezone(_GUATEMALA)
    return f"{today.day} de {_MONTHS[today.month - 1]} de {today.year}"


class AnswerQuestionUseCase:
    def __init__(
        self,
        conversation_repository: ConversationRepositoryPort,
        document_repository: DocumentRepositoryPort,
        context_retrieval: ContextRetrieval,
        verification_port: VerificationStrategyPort,
        query_rewriter: QueryRewriter,
        indexed_chunk_count: int,
        history_turns: int = 6,
    ) -> None:
        self._conversations = conversation_repository
        self._documents = document_repository
        self._retrieval = context_retrieval
        self._verification = verification_port
        self._rewriter = query_rewriter
        self._indexed_chunk_count = indexed_chunk_count
        self._history_turns = history_turns

    async def execute(self, request: AnswerQueryRequest) -> AnswerQueryResponse:
        started_at = time.perf_counter()
        conversation = await self._conversations.get_or_create_active_conversation(request.user_id)
        history = await self._load_history(request.user_id, conversation.id)

        sanitized = MessageSanitizer.sanitize(request.question)
        await self._conversations.add_message(
            conversation.id,
            Message(
                id=new_id(),
                conversation_id=conversation.id,
                role=MessageRole.STUDENT,
                content=sanitized.original or request.question,
                created_at=utc_now(),
            ),
        )

        smalltalk = self._smalltalk(sanitized.original)
        if smalltalk is not None:
            return await self._reply(conversation.id, smalltalk, AnswerStatus.SMALLTALK, started_at)

        if self._indexed_chunk_count == 0:
            return await self._reply(conversation.id, NO_DOCUMENTS_MESSAGE, AnswerStatus.NO_DOCUMENTS, started_at)

        question = sanitized.safe_for_prompt or sanitized.original
        rewritten = await self._rewriter.rewrite(question, history)
        search_query = rewritten.text
        if rewritten.is_follow_up:
            logger.info("Seguimiento reescrito ({}): '{}' → '{}'", rewritten.method, question, search_query)

        retrieval_started = time.perf_counter()
        context = await self._retrieval.retrieve(search_query)
        ranked, passages = context.candidates, context.passages
        retrieval_seconds = time.perf_counter() - retrieval_started
        logger.info(
            "Recuperación: {} candidatos, {} pasajes en contexto ({:.2f}s)",
            len(ranked),
            len(passages),
            retrieval_seconds,
        )

        if not passages:
            return await self._reply(
                conversation.id, NO_EVIDENCE_MESSAGE, AnswerStatus.ABSTAINED, started_at,
                is_grounded=False, confidence=VerificationConfidence.LOW, search_query=search_query,
            )

        model_question = question
        if rewritten.is_follow_up and search_query != question:
            model_question = f"{question}\n\n(Interpretación de la pregunta: {search_query})"
        model_question = f"{model_question}\n\n(Fecha de hoy: {_today_in_guatemala()}.)"

        try:
            answer = await self._verification.answer(
                model_question,
                passages,
                conversation=format_history(history) if history else None,
            )
        except LLMNotConfiguredError as error:
            logger.error("Claude no está configurado: {}", error)
            return await self._reply(
                conversation.id, NOT_CONFIGURED_MESSAGE, AnswerStatus.ERROR, started_at, search_query=search_query
            )
        except LLMUnavailableError as error:
            logger.error("Claude no disponible: {}", error)
            return await self._reply(
                conversation.id, UNAVAILABLE_MESSAGE, AnswerStatus.ERROR, started_at, search_query=search_query
            )
        except (LLMGenerationError, VerificationFailedError) as error:
            logger.error("La generación falló: {}", error)
            return await self._reply(
                conversation.id, GENERATION_FAILED_MESSAGE, AnswerStatus.ERROR, started_at, search_query=search_query
            )

        logger.info(
            "Generación: grounded={}, cobertura={}, confianza={}, citados={}, tokens={}/{}",
            answer.is_grounded,
            answer.coverage.value,
            answer.confidence.value,
            list(answer.cited_fragments),
            answer.input_tokens,
            answer.output_tokens,
        )

        if not answer.is_grounded or answer.coverage is AnswerCoverage.NONE:
            return await self._reply(
                conversation.id,
                NOT_GROUNDED_MESSAGE + self._nearest_hint(passages),
                AnswerStatus.ABSTAINED,
                started_at,
                is_grounded=False,
                confidence=answer.confidence,
                search_query=search_query,
            )

        cited = self._cited_passages(answer, passages)
        sources = await self._resolve_sources(cited)
        confidence = answer.confidence
        if answer.coverage is AnswerCoverage.PARTIAL and confidence is VerificationConfidence.HIGH:
            confidence = VerificationConfidence.MEDIUM
        return await self._reply(
            conversation.id,
            answer.answer_text,
            AnswerStatus.ANSWERED,
            started_at,
            is_grounded=True,
            confidence=confidence,
            sources=sources,
            source_chunk_ids=tuple(dict.fromkeys(cid for p in cited for cid in p.origin_ids)),
            search_query=search_query,
        )

    # --- Apoyo ---------------------------------------------------------------------------

    async def _load_history(self, user_id: UUID, conversation_id: UUID) -> Sequence[Message]:
        for candidate in await self._conversations.get_history(user_id):
            if candidate.id == conversation_id:
                return tuple(candidate.messages)[-self._history_turns * 2 :]
        return ()

    def _smalltalk(self, message: str) -> str | None:
        folded = fold(message).strip()
        if not folded:
            return "Escribe tu pregunta sobre la universidad y con gusto te ayudo."
        if _GREETING.match(folded) or _IDENTITY.match(folded):
            return (
                "¡Hola! Soy **UVG ONE**, el orientador virtual de la Universidad del Valle de Guatemala, "
                "Campus Altiplano. Respondo con base en los documentos oficiales de la universidad.\n\n"
                "Puedes preguntarme, por ejemplo, por:\n"
                "- **Carreras** y lo que ofrece cada programa\n"
                "- **Admisión e inscripción** de primer ingreso\n"
                "- **Calendario académico** y fechas importantes\n"
                "- **Ayudas financieras**, reglamentos y grupos estudiantiles\n\n"
                "¿Qué te gustaría saber?"
            )
        if _THANKS.match(folded):
            return "Con gusto. Si tienes otra duda sobre la universidad, aquí estoy."
        if _FAREWELL.match(folded):
            return "¡Hasta pronto! Vuelve cuando necesites información de la universidad."
        return None

    @staticmethod
    def _cited_passages(answer: VerifiedAnswer, passages: Sequence[RetrievedChunk]) -> list[RetrievedChunk]:
        """Solo se citan los pasajes en que el modelo dice apoyarse; si no lo indica, todos."""
        cited = [passages[index - 1] for index in answer.cited_fragments if 1 <= index <= len(passages)]
        return cited or list(passages)

    @staticmethod
    def _nearest_hint(passages: Sequence[RetrievedChunk]) -> str:
        for passage in passages:
            chunk = passage.chunk
            if chunk.document and chunk.document.title:
                where = f" ({chunk.anchor.citation_label})" if chunk.anchor and chunk.anchor.citation_label else ""
                return f"\n\nLo más cercano que encontré está en **{chunk.document.title}**{where}, por si quieres revisarlo."
        return ""

    async def _resolve_sources(self, passages: Sequence[RetrievedChunk]) -> tuple[SourceReference, ...]:
        filenames = {document.id: document.filename for document in await self._documents.list_all()}
        unique: dict[tuple[str, str, int | None], SourceReference] = {}
        for passage in passages:
            chunk = passage.chunk
            filename = filenames.get(chunk.document_id)
            if filename is None:
                continue
            reference = SourceReference.at(
                document_name=filename,
                document_id=chunk.document_id,
                document_title=chunk.document.title if chunk.document else None,
                anchor=chunk.anchor,
            )
            unique.setdefault(reference.dedup_key, reference)
        return tuple(unique.values())

    async def _reply(
        self,
        conversation_id: UUID,
        text: str,
        status: AnswerStatus,
        started_at: float,
        *,
        is_grounded: bool | None = None,
        confidence: VerificationConfidence | None = None,
        sources: tuple[SourceReference, ...] = (),
        source_chunk_ids: tuple[UUID, ...] = (),
        search_query: str | None = None,
    ) -> AnswerQueryResponse:
        message = Message(
            id=new_id(),
            conversation_id=conversation_id,
            role=MessageRole.ASSISTANT,
            content=text,
            created_at=utc_now(),
            is_grounded=is_grounded,
            confidence=confidence,
            source_chunk_ids=source_chunk_ids,
            source_document_names=tuple(dict.fromkeys(s.document_name for s in sources)),
            sources=sources,
        )
        await self._conversations.add_message(conversation_id, message)
        logger.info("Respuesta '{}' en {:.2f}s", status.value, time.perf_counter() - started_at)
        return AnswerQueryResponse(
            message_id=message.id,
            conversation_id=conversation_id,
            answer_text=text,
            status=status,
            is_grounded=is_grounded,
            confidence=confidence,
            created_at=message.created_at,
            sources=sources,
            search_query=search_query,
        )
