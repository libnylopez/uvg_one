from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel

from app.application.services.context_retrieval import ContextRetrieval
from app.domain.services.message_sanitizer import MessageSanitizer
from app.infrastructure.entrypoints.api.dependencies import get_context_retrieval

router = APIRouter(prefix="/search", tags=["search"])


class PassageSchema(BaseModel):
    rank: int
    document: str
    section: str | None
    page: int | None
    page_end: int | None = None
    similarity: float
    lexical_coverage: float
    text: str


class SearchResultSchema(BaseModel):
    query: str
    candidates: int
    is_overview: bool
    passages: list[PassageSchema]


@router.get("", response_model=SearchResultSchema)
async def search(
    retrieval: Annotated[ContextRetrieval, Depends(get_context_retrieval)],
    q: str = Query(min_length=1, max_length=500),
    topic: str | None = Query(default=None, max_length=500, description="Tema vigente si q es un seguimiento"),
) -> SearchResultSchema:
    """Solo la parte de recuperación del RAG (sin Claude): qué pasajes llegarían al modelo."""
    # Mismo saneamiento que el chat (corrección ortográfica y abreviaturas).
    context = await retrieval.retrieve(MessageSanitizer.sanitize(q).safe_for_prompt or q, topic=topic)
    passages = context.passages
    return SearchResultSchema(
        query=q,
        candidates=len(context.candidates),
        is_overview=context.is_overview,
        passages=[
            PassageSchema(
                rank=index + 1,
                document=p.chunk.document.title if p.chunk.document else str(p.chunk.document_id),
                section=p.chunk.anchor.citation_label if p.chunk.anchor else None,
                page=p.chunk.anchor.page_start if p.chunk.anchor else None,
                page_end=(p.chunk.anchor.page_end or p.chunk.anchor.page_start) if p.chunk.anchor else None,
                similarity=round(p.score.value, 3),
                lexical_coverage=round(p.lexical_coverage, 3),
                text=p.chunk.text,
            )
            for index, p in enumerate(passages)
        ],
    )
