"""Recuperación de contexto para una consulta: lo que realmente se le entrega a Claude.

Lo usan el chat y el endpoint de diagnóstico /search, para que ambos muestren lo mismo.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from loguru import logger

from app.application.services.context_assembler import ContextAssembler
from app.application.services.knowledge_retriever import KnowledgeRetriever
from app.domain.entities.chunk import RetrievedChunk
from app.domain.ports.corpus_catalog_port import CorpusCatalogPort
from app.domain.services.query_analyzer import QueryAnalysis, QueryAnalyzer
from app.domain.services.spanish_text import fold
from app.domain.value_objects.document_facts import DocumentKind

# «¿Qué carreras ofrece?», «¿qué programas hay?»: la respuesta está repartida en un folleto por
# programa, así que se toma el mejor fragmento de cada uno en vez de varios del mismo.
_PROGRAM_OVERVIEW = re.compile(
    r"\b(?:que|cuales|cuantas|cuantos|todas|todos|lista\w*|opciones|oferta)\b.*"
    r"\b(?:carreras|programas|licenciaturas|profesorados|ingenierias|maestrias|opciones de estudio|oferta academica)\b"
    r"|\b(?:carreras|programas|oferta academica|opciones de estudio)\b.*"
    r"\b(?:ofrece\w*|hay|tiene\w*|existen|disponibles|imparte\w*)\b"
)
_NON_PROGRAM_KINDS = frozenset({DocumentKind.REGULATION, DocumentKind.CALENDAR, DocumentKind.PROCESS})
_MAX_OVERVIEW_DOCUMENTS = 16


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

    async def retrieve(self, query: str) -> RetrievedContext:
        outlines = self._catalog.list_outlines() if self._catalog else []
        analysis = QueryAnalyzer.analyze(query, outlines)

        overview: list[RetrievedChunk] = []
        if _PROGRAM_OVERVIEW.search(fold(query)):
            brochures = [o.document_id for o in outlines if o.kind not in _NON_PROGRAM_KINDS]
            overview = await self._retriever.best_per_document(query, brochures[:_MAX_OVERVIEW_DOCUMENTS])
            logger.info("Panorama de programas: {} de {} folletos aportan evidencia", len(overview), len(brochures))

        if overview:
            # Un panorama necesita más pasajes que una pregunta puntual.
            return RetrievedContext(analysis, overview, self._assembler.assemble(overview, parts=2), True)

        candidates = await self._retriever.retrieve(analysis)
        passages = self._assembler.assemble(candidates, parts=len(analysis.sub_queries))
        return RetrievedContext(analysis, candidates, passages, False)
