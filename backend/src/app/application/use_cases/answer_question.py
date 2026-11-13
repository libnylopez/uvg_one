"""Caso de uso principal de UVG ONE: conversar y responder preguntas con RAG.

Flujo por mensaje:
  1. Saneamiento y clasificación local de la intención (sin LLM).
  2. Saludo, cortesía, identidad, ayuda, gracias o despedida → respuesta local (0 tokens).
  3. Consulta: si depende de la conversación, se completa con el tema vigente (local, 0 tokens).
  4. Recuperación híbrida (semántica + léxica) y ensamblado del contexto.
  5. Sin evidencia suficiente → abstención, sin llamar al modelo.
  6. Claude responde y autoverifica en una sola llamada con salida estructurada.
  7. No fundamentada → abstención. Fundamentada → respuesta + fuentes citadas (documento y página).
"""

from __future__ import annotations

import re
import time
from collections.abc import Sequence
from dataclasses import dataclass, replace
from datetime import datetime, timedelta, timezone
from uuid import UUID

from loguru import logger

from app.application.dto.chat_dto import AnswerQueryRequest, AnswerQueryResponse, AnswerStatus, AnswerUsage
from app.application.services.context_retrieval import ContextRetrieval
from app.application.services.query_rewriter import LocalFollowUpResolver, QueryRewriter, format_history
from app.application.services.social_replies import courtesy_prefix, social_reply
from app.domain.entities.chunk import RetrievedChunk
from app.domain.entities.message import Message, MessageRole
from app.domain.ports.conversation_repository_port import ConversationRepositoryPort
from app.domain.ports.document_repository_port import DocumentRepositoryPort
from app.domain.ports.verification_strategy_port import VerificationStrategyPort
from app.domain.services.conversational_intent import classify
from app.domain.services.message_sanitizer import MessageSanitizer
from app.domain.services.spanish_text import fold
from app.domain.value_objects.llm_completion import LLMCompletion
from app.domain.value_objects.source_reference import SourceReference
from app.domain.value_objects.verified_answer import AnswerCoverage, VerificationConfidence, VerifiedAnswer
from app.shared.exceptions.domain_errors import (
    LLMBudgetExceededError,
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
    "específico, por ejemplo: «requisitos de admisión para primer ingreso» o «fechas del calendario académico»."
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
    "El servicio de inteligencia artificial no está disponible: falta o fue rechazada la API key de "
    "Anthropic, o la cuenta no tiene saldo. La búsqueda en documentos funciona, pero no puedo redactar la respuesta."
)
BUDGET_MESSAGE = (
    "Se alcanzó el presupuesto de uso de la API configurado para este prototipo, así que no puedo "
    "redactar más respuestas por ahora. Los saludos y la búsqueda de documentos siguen funcionando."
)
UNAVAILABLE_MESSAGE = (
    "El servicio de inteligencia artificial no está disponible en este momento. "
    "Espera unos segundos y vuelve a intentarlo."
)
GENERATION_FAILED_MESSAGE = (
    "Tuve un problema al preparar la respuesta. Vuelve a intentarlo; si el problema continúa, "
    "reformula la pregunta."
)

# Datos de una respuesta que sirven para ubicar su página: números, correos y palabras de 5+ letras.
_ANSWER_TERM = re.compile(r"[\w.+-]+@[\w.-]+|\d+(?:[.,]\d+)?|[a-zñ]{5,}")
_WORD = re.compile(r"[\w@.+-]*\w")

_GUATEMALA = timezone(timedelta(hours=-6))
_MONTHS = ("enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto",
           "septiembre", "octubre", "noviembre", "diciembre")


def _today_in_guatemala(now: datetime | None = None) -> str:
    today = (now or datetime.now(_GUATEMALA)).astimezone(_GUATEMALA)
    return f"{today.day} de {_MONTHS[today.month - 1]} de {today.year}"


@dataclass(slots=True)
class _UsageMeter:
    calls: int = 0
    input_tokens: int = 0
    output_tokens: int = 0
    cost_usd: float = 0.0
    model: str | None = None
    simulated: bool = False

    def add(self, *, input_tokens: int | None, output_tokens: int | None, cost: float, model: str | None,
            simulated: bool) -> None:
        self.calls += 1
        self.input_tokens += input_tokens or 0
        self.output_tokens += output_tokens or 0
        self.cost_usd += cost
        self.model = model or self.model
        self.simulated = self.simulated or simulated

    def add_completion(self, completion: LLMCompletion | None) -> None:
        if completion is not None:
            self.add(input_tokens=completion.input_tokens, output_tokens=completion.output_tokens,
                     cost=completion.cost_usd, model=completion.model, simulated=completion.simulated)

    def freeze(self) -> AnswerUsage:
        return AnswerUsage(self.calls, self.input_tokens, self.output_tokens, round(self.cost_usd, 8),
                           self.model, self.simulated)


class AnswerQuestionUseCase:
    def __init__(
        self,
        conversation_repository: ConversationRepositoryPort,
        document_repository: DocumentRepositoryPort,
        context_retrieval: ContextRetrieval,
        verification_port: VerificationStrategyPort,
        query_rewriter: QueryRewriter | LocalFollowUpResolver,
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
        reply = _Replier(self, conversation.id, started_at)

        # 1-2. Conversación social: se resuelve localmente, sin búsqueda ni API.
        intent = classify(sanitized.original)
        if intent.is_social:
            assistant_turns = sum(1 for m in history if m.role is MessageRole.ASSISTANT)
            return await reply(
                social_reply(intent.kind, assistant_turns), AnswerStatus.SMALLTALK, intent=intent.kind.value,
                topic=self._current_topic(history),
            )

        if self._indexed_chunk_count == 0:
            return await reply(NO_DOCUMENTS_MESSAGE, AnswerStatus.NO_DOCUMENTS)

        # 3. Seguimiento: completar la consulta con el tema vigente.
        question = MessageSanitizer.sanitize(intent.query).safe_for_prompt or intent.query
        usage = _UsageMeter()
        rewritten = await self._rewriter.rewrite(question, history)
        usage.add_completion(rewritten.completion)
        search_query = rewritten.text
        kind = "seguimiento" if rewritten.is_follow_up else "consulta"
        if rewritten.is_follow_up:
            logger.info("Seguimiento ({}): '{}' → búsqueda '{}'", rewritten.method, question, search_query)

        # 4. Recuperación.
        retrieval_started = time.perf_counter()
        context = await self._retrieval.retrieve(search_query, topic=rewritten.topic if rewritten.is_follow_up else None)
        passages = context.passages
        logger.info(
            "Recuperación: {} candidatos, {} pasajes, {} caracteres de contexto ({:.2f}s)",
            len(context.candidates), len(passages), sum(len(p.chunk.text) for p in passages),
            time.perf_counter() - retrieval_started,
        )
        common = {"intent": kind, "search_query": search_query, "topic": rewritten.topic, "usage": usage}

        # 5. Sin evidencia: abstención sin gastar una llamada.
        if not passages:
            return await reply(NO_EVIDENCE_MESSAGE, AnswerStatus.ABSTAINED, is_grounded=False,
                               confidence=VerificationConfidence.LOW, **common)

        # 6. Claude: respuesta y autoverificación.
        model_question = question
        if rewritten.is_follow_up:
            model_question = f"{question}\n\n(Es una pregunta de seguimiento sobre: {rewritten.topic})"
        model_question = f"{model_question}\n\n(Fecha de hoy: {_today_in_guatemala()}.)"
        try:
            answer = await self._verification.answer(
                model_question, passages, conversation=format_history(history) if history else None
            )
        except LLMBudgetExceededError as error:
            logger.error("Presupuesto agotado: {}", error)
            return await reply(BUDGET_MESSAGE, AnswerStatus.ERROR, **common)
        except LLMNotConfiguredError as error:
            logger.error("Claude no está configurado: {}", error)
            return await reply(NOT_CONFIGURED_MESSAGE, AnswerStatus.ERROR, **common)
        except LLMUnavailableError as error:
            logger.error("Claude no disponible: {}", error)
            return await reply(UNAVAILABLE_MESSAGE, AnswerStatus.ERROR, **common)
        except (LLMGenerationError, VerificationFailedError) as error:
            logger.error("La generación falló: {}", error)
            return await reply(GENERATION_FAILED_MESSAGE, AnswerStatus.ERROR, **common)

        usage.add(input_tokens=answer.input_tokens, output_tokens=answer.output_tokens, cost=answer.cost_usd,
                  model=answer.model, simulated=answer.simulated)
        logger.info(
            "Generación: grounded={}, cobertura={}, confianza={}, citados={}",
            answer.is_grounded, answer.coverage.value, answer.confidence.value, list(answer.cited_fragments),
        )

        # 7. Abstención o respuesta con fuentes.
        if not answer.is_grounded or answer.coverage is AnswerCoverage.NONE:
            return await reply(NOT_GROUNDED_MESSAGE + self._nearest_hint(passages), AnswerStatus.ABSTAINED,
                               is_grounded=False, confidence=answer.confidence, **common)

        cited = self._cited_passages(answer, passages)
        sources = await self._resolve_sources(cited, answer.answer_text)
        confidence = answer.confidence
        if answer.coverage is AnswerCoverage.PARTIAL and confidence is VerificationConfidence.HIGH:
            confidence = VerificationConfidence.MEDIUM
        text = answer.answer_text
        prefix = courtesy_prefix(intent.social_prefix)
        if prefix and not text.lstrip().startswith("¡"):
            text = f"{prefix} {text}"
        return await reply(
            text, AnswerStatus.ANSWERED, is_grounded=True, confidence=confidence, sources=sources,
            source_chunk_ids=tuple(dict.fromkeys(cid for p in cited for cid in p.origin_ids)), **common,
        )

    # --- Apoyo ---------------------------------------------------------------------------

    async def _load_history(self, user_id: UUID, conversation_id: UUID) -> Sequence[Message]:
        for candidate in await self._conversations.get_history(user_id):
            if candidate.id == conversation_id:
                return tuple(candidate.messages)[-self._history_turns * 2 :]
        return ()

    @staticmethod
    def _current_topic(history: Sequence[Message]) -> str | None:
        """Un saludo en medio de la conversación no borra el tema vigente."""
        return next((m.topic_query for m in reversed(history) if m.topic_query), None)

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

    def _precise_anchor(self, passage: RetrievedChunk, answer_text: str):
        """Página exacta de un pasaje fusionado que abarca varias páginas.

        El ensamblador une fragmentos contiguos (p. ej. agosto en la pág. 2 y septiembre en la 3 del
        calendario). Se cita la página del fragmento original que contiene los datos de la respuesta;
        si no hay uno claramente mejor, se conserva el rango completo, que también es verdadero.
        """
        anchor = passage.chunk.anchor
        if anchor is None or anchor.page_start is None or anchor.page_end in (None, anchor.page_start):
            return anchor
        originals = [c for c in self._retrieval.origin_chunks(passage.origin_ids) if c.anchor and c.anchor.page_start]
        if len(originals) < 2:
            return anchor
        words = _WORD.findall(fold(answer_text))
        # Secuencias de tres palabras de la respuesta («17 de septiembre»): distinguen el fragmento
        # exacto mejor que palabras sueltas, que se repiten en todo el documento («último día para pagar»).
        trigrams = {" ".join(words[i:i + 3]) for i in range(len(words) - 2)}
        terms = set(_ANSWER_TERM.findall(fold(answer_text)))

        def score(chunk) -> tuple[int, int]:
            text = " ".join(_WORD.findall(fold(chunk.text)))
            return sum(1 for t in trigrams if t in text), sum(1 for t in terms if t in text)

        scored = sorted(((score(c), c) for c in originals), key=lambda pair: pair[0], reverse=True)
        (best_score, best), runner_up = scored[0], scored[1][0]
        if best_score[0] == 0 or best_score == runner_up:
            return anchor
        return replace(anchor, page_start=best.anchor.page_start, page_end=best.anchor.page_end or best.anchor.page_start)

    async def _resolve_sources(
        self, passages: Sequence[RetrievedChunk], answer_text: str = ""
    ) -> tuple[SourceReference, ...]:
        """Una referencia por ubicación citada. Una página fuera del documento no se muestra."""
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
                anchor=self._precise_anchor(passage, answer_text) if answer_text else chunk.anchor,
            )
            page_count = chunk.document.page_count if chunk.document else None
            if reference.page_number is not None and (
                reference.page_number < 1 or (page_count and reference.page_number > page_count)
            ):
                reference = SourceReference(reference.document_name, None, reference.document_id,
                                            reference.document_title, reference.section, None)
            unique.setdefault(reference.dedup_key, reference)
        return tuple(unique.values())

    async def _persist(
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
        intent: str = "consulta",
        topic: str | None = None,
        usage: _UsageMeter | None = None,
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
            topic_query=topic,
            status=status.value,
        )
        await self._conversations.add_message(conversation_id, message)
        frozen = (usage or _UsageMeter()).freeze()
        logger.info(
            "Respuesta '{}' ({}) en {:.2f}s · llamadas a Claude={} tokens={}/{} costo≈US${:.5f}",
            status.value, intent, time.perf_counter() - started_at,
            frozen.llm_calls, frozen.input_tokens, frozen.output_tokens, frozen.cost_usd,
        )
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
            intent=intent,
            topic=topic,
            usage=frozen,
        )


class _Replier:
    """Atajo para persistir y construir la respuesta con el contexto de la petición."""

    def __init__(self, use_case: AnswerQuestionUseCase, conversation_id: UUID, started_at: float) -> None:
        self._use_case, self._conversation_id, self._started_at = use_case, conversation_id, started_at

    async def __call__(self, text: str, status: AnswerStatus, **kwargs: object) -> AnswerQueryResponse:
        return await self._use_case._persist(self._conversation_id, text, status, self._started_at, **kwargs)  # type: ignore[arg-type]
