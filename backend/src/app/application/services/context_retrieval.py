"""Recuperación de contexto para una consulta: lo que realmente se le entrega a Claude.

Lo usan el chat y el endpoint de diagnóstico /search, para que ambos muestren lo mismo.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, replace
from uuid import UUID

from loguru import logger

from app.application.services.context_assembler import ContextAssembler
from app.application.services.knowledge_retriever import KnowledgeRetriever
from app.domain.entities.chunk import Chunk, RetrievedChunk
from app.domain.ports.corpus_catalog_port import CorpusCatalogPort
from app.domain.services.institutional_lexicon import expansions_for
from app.domain.services.query_analyzer import QueryAnalysis, QueryAnalyzer
from app.domain.services.spanish_text import fold
from app.domain.value_objects.document_facts import DocumentKind

# «¿Qué carreras ofrece?», «¿qué programas hay?»: la respuesta está repartida en un folleto por
# programa, así que se toma el mejor fragmento de cada uno en vez de varios del mismo.
_PROGRAM_OVERVIEW = re.compile(
    # Solo preguntas generales. Una familia concreta («¿qué ingenierías hay?») se responde mejor con la
    # búsqueda normal, que trae justo esos folletos (medido con evaluacion/benchmark_recuperacion.json).
    r"\b(?:que|cuales|cuantas|cuantos|todas|todos|lista\w*|opciones|oferta)\b.*"
    r"\b(?:carreras|programas|opciones de estudio|oferta academica)\b"
    r"|\b(?:carreras|programas|oferta academica|opciones de estudio)\b.*"
    r"\b(?:ofrece\w*|hay|tiene\w*|existen|disponibles|imparte\w*)\b"
    r"|\bque (?:puedo|se puede) estudiar\b"
)
_NON_PROGRAM_KINDS = frozenset({DocumentKind.REGULATION, DocumentKind.CALENDAR, DocumentKind.PROCESS})
_MAX_OVERVIEW_DOCUMENTS = 16
# Fragmentos propios por folleto en un panorama: uno solo (≈200 caracteres) no alcanzaba para
# responder «¿qué ingenierías hay y cuánto duran?».
_OVERVIEW_PER_DOCUMENT = 2
# Pregunta que nombra un documento pero no supera el umbral de evidencia («¿cuánto dura la maestría?»):
# se busca dentro de ese documento.
_NAMED_DOCUMENT_PASSAGES = 4
_MAX_NAMED_DOCUMENTS = 2
# «… y cuánto duran?», «… y dónde me informo?»: una pregunta con una cola de aspecto.
_ASPECT_TAIL = re.compile(
    r"^(.*\S)\s+y\s+((?:cu[aá]nt|cu[aá]nd|d[oó]nde|c[oó]mo|qu[eé]|cu[aá]l)\w*\b.*)$", re.IGNORECASE
)
# Documentos de la 1.ª parte en los que se busca el aspecto («¿qué ingenierías… y cuánto duran?»).
_ASPECT_DOCUMENTS = 5
# Documentos del tema vigente a los que se restringe un seguimiento.
_TOPIC_DOCUMENTS = 3


@dataclass(frozen=True, slots=True)
class RetrievedContext:
    analysis: QueryAnalysis
    candidates: list[RetrievedChunk]
    passages: list[RetrievedChunk]
    is_overview: bool


class ContextRetrieval:
    def __init__(
        self,
        retriever: KnowledgeRetriever,
        assembler: ContextAssembler,
        catalog: CorpusCatalogPort | None,
    ) -> None:
        self._retriever = retriever
        self._assembler = assembler
        self._catalog = catalog

    def origin_chunks(self, chunk_ids: tuple[UUID, ...]) -> list[Chunk]:
        """Fragmentos originales de un pasaje fusionado (para ubicar la página exacta de una cita)."""
        return self._catalog.chunks_by_ids(list(chunk_ids)) if self._catalog else []

    async def retrieve(self, query: str, topic: str | None = None) -> RetrievedContext:
        """`topic`: tema de la conversación cuando `query` es un seguimiento.

        Un seguimiento («¿cuánto dura esa carrera?») se busca dentro de los documentos del tema:
        si no, frases genéricas como «cuánto dura» encuentran cualquier documento que hable de
        plazos (p. ej. un artículo del reglamento de ayudas financieras) y el referente se pierde.
        """
        outlines = self._catalog.list_outlines() if self._catalog else []
        analysis = self._complete_sub_queries(QueryAnalyzer.analyze(query, outlines))

        if topic:
            focused = await self._within_topic(query, topic, analysis)
            if focused is not None:
                return focused

        overview: list[RetrievedChunk] = []
        if _PROGRAM_OVERVIEW.search(fold(query)):
            brochures = [o.document_id for o in outlines if o.kind not in _NON_PROGRAM_KINDS]
            overview = await self._retriever.best_per_document(
                query, brochures[:_MAX_OVERVIEW_DOCUMENTS], keep=_OVERVIEW_PER_DOCUMENT
            )
            logger.info("Panorama de programas: {} pasajes de {} folletos", len(overview), len(brochures))

        if overview:
            # Un panorama necesita más pasajes que una pregunta puntual.
            return RetrievedContext(analysis, overview, self._assembler.assemble(overview, parts=2), True)

        aspect_context = await self._aspect_within_subject(query, analysis)
        if aspect_context is not None:
            return aspect_context

        candidates = await self._retriever.retrieve(analysis)
        named = list(dict.fromkeys((*analysis.target_documents, *analysis.preferred_documents)))[:_MAX_NAMED_DOCUMENTS]
        if not candidates and named:
            # Sin evidencia fuerte en todo el corpus, pero la pregunta nombra el documento.
            candidates = await self._retriever.best_per_document(
                query, named, per_document=_NAMED_DOCUMENT_PASSAGES, keep=_NAMED_DOCUMENT_PASSAGES
            )
            logger.info("Búsqueda dentro del documento nombrado: {} pasajes", len(candidates))
        passages = self._assembler.assemble(candidates, parts=len(analysis.sub_queries))
        return RetrievedContext(analysis, candidates, passages, False)

    async def _aspect_within_subject(self, query: str, analysis: QueryAnalysis) -> RetrievedContext | None:
        """«¿Qué ingenierías hay y cuánto duran?»: la duración se busca dentro de los folletos hallados.

        La 1.ª parte encuentra los documentos; la parte de aspecto, buscada en todo el corpus, solo
        repetiría las portadas. Se busca en cada documento con el aspecto y sus sinónimos
        («años», «total de la carrera»).
        """
        from app.application.services.query_rewriter import LocalFollowUpResolver  # evita import circular

        resolver = LocalFollowUpResolver()
        if analysis.is_multi_part:
            first, *rest = analysis.sub_queries
            aspects = [part.removesuffix(f" {first}") for part in rest]
        else:
            match = _ASPECT_TAIL.match(query.strip())
            if not match:
                return None
            first, aspects = match.group(1), [match.group(2)]
        aspects = [part for part in aspects if resolver.depends_on_context(part)]
        if not aspects:
            return None
        base = await self._retriever.retrieve(replace(analysis, text=first, sub_queries=(first,)))
        documents = list(dict.fromkeys(item.chunk.document_id for item in base))[:_ASPECT_DOCUMENTS]
        if not documents:
            return None
        extra: list[RetrievedChunk] = []
        for aspect in aspects:
            terms = [fold(t) for t in expansions_for(fold(aspect))]
            expanded = " ".join((aspect, *terms))
            pool = await self._retriever.best_per_document(expanded, documents, per_document=6, keep=6)
            # Por documento, el fragmento que menciona el aspecto («años», «total de la carrera»);
            # a igualdad, el más parecido semánticamente.
            for document in documents:
                own = [item for item in pool if item.chunk.document_id == document]
                if own:
                    extra.append(max(own, key=lambda item: (sum(t in fold(item.chunk.text) for t in terms),
                                                            item.score.value)))
        head = base[:len(documents)]
        seen = {item.chunk.id for item in head}
        aspect_items = [item for item in extra if item.chunk.id not in seen]
        seen |= {item.chunk.id for item in aspect_items}
        # Primero lo mejor de cada parte (el ensamblador recorta por orden), luego el resto.
        ordered = [*head, *aspect_items, *(item for item in base if item.chunk.id not in seen)]
        logger.info("Aspecto buscado dentro de {} documento(s) de la 1.ª parte: {} pasajes", len(documents), len(aspect_items))
        return RetrievedContext(analysis, ordered, self._assembler.assemble(ordered, parts=1 + len(aspects)), False)

    @staticmethod
    def _complete_sub_queries(analysis: QueryAnalysis) -> QueryAnalysis:
        """«¿Qué ingenierías hay y cuánto duran?» → la 2.ª parte hereda el tema de la 1.ª.

        Sola, «cuánto duran» encuentra cualquier documento con una duración (p. ej. la maestría).
        """
        if not analysis.is_multi_part:
            return analysis
        from app.application.services.query_rewriter import LocalFollowUpResolver  # evita import circular

        resolver = LocalFollowUpResolver()
        first, *rest = analysis.sub_queries
        completed = [first, *(f"{part} {first}" if resolver.depends_on_context(part) else part for part in rest)]
        return replace(analysis, sub_queries=tuple(completed))

    async def _within_topic(self, query: str, topic: str, analysis: QueryAnalysis) -> RetrievedContext | None:
        if analysis.target_documents:
            return None  # el seguimiento nombra su propio documento
        topic_context = await self.retrieve(topic)
        named = (*topic_context.analysis.target_documents, *topic_context.analysis.preferred_documents)
        order = list(dict.fromkeys(p.chunk.document_id for p in topic_context.passages))
        if named and not topic_context.is_overview:
            # El tema nombra su documento («la Licenciatura en Turismo»): el seguimiento es de ese documento.
            documents: list[UUID] = list(dict.fromkeys(named))[:_TOPIC_DOCUMENTS]
        else:
            documents = order if topic_context.is_overview else order[:_TOPIC_DOCUMENTS]
        if not documents:
            return None
        candidates = await self._retriever.retrieve(replace(analysis, target_documents=tuple(documents)))
        if not candidates:
            candidates = await self._retriever.best_per_document(
                query, documents, per_document=_NAMED_DOCUMENT_PASSAGES, keep=2
            )
        if not candidates:
            return None
        logger.info("Seguimiento buscado dentro de {} documento(s) del tema", len(documents))
        passages = self._assembler.assemble(candidates, parts=max(1, len(analysis.sub_queries)))
        return RetrievedContext(analysis, candidates, passages, False)
