"""Proveedores de dependencias de FastAPI: el único lugar que conecta adaptadores con casos de uso."""

from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import Depends, Header, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.application.services.context_retrieval import ContextRetrieval
from app.application.services.query_rewriter import QueryRewriter
from app.application.use_cases.answer_question import AnswerQuestionUseCase
from app.application.use_cases.start_guest_session import StartGuestSessionUseCase
from app.domain.entities.user import User
from app.domain.ports.auth_port import AuthPort
from app.domain.ports.conversation_repository_port import ConversationRepositoryPort
from app.domain.ports.document_repository_port import DocumentRepositoryPort
from app.domain.ports.user_repository_port import UserRepositoryPort
from app.infrastructure.adapters.persistence.database import get_db_session
from app.infrastructure.adapters.persistence.postgres_conversation_repository import (
    PostgresConversationRepository,
)
from app.infrastructure.adapters.persistence.postgres_document_repository import (
    PostgresDocumentRepository,
)
from app.infrastructure.adapters.persistence.postgres_user_repository import PostgresUserRepository
from app.infrastructure.config.settings import get_app_settings, get_auth_settings, get_rag_settings
from app.infrastructure.rag_factory import build_context_assembler, build_retriever
from app.shared.exceptions.domain_errors import UnauthorizedError


def get_auth_port(request: Request) -> AuthPort:
    return request.app.state.auth_port


def get_user_repository(session: Annotated[AsyncSession, Depends(get_db_session)]) -> UserRepositoryPort:
    return PostgresUserRepository(session)


def get_conversation_repository(
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> ConversationRepositoryPort:
    return PostgresConversationRepository(session)


def get_document_repository(
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> DocumentRepositoryPort:
    return PostgresDocumentRepository(session)


def get_start_guest_session_use_case(
    user_repository: Annotated[UserRepositoryPort, Depends(get_user_repository)],
    auth_port: Annotated[AuthPort, Depends(get_auth_port)],
) -> StartGuestSessionUseCase:
    return StartGuestSessionUseCase(user_repository, auth_port, get_auth_settings())


def get_context_retrieval(request: Request) -> ContextRetrieval:
    state = request.app.state
    rag_settings = get_rag_settings()
    lexical = state.corpus_index if rag_settings.retrieval_mode == "hybrid" else None
    return ContextRetrieval(
        retriever=build_retriever(state.embedding_port, state.vector_store_port, lexical, rag_settings),
        assembler=build_context_assembler(state.corpus_index, rag_settings),
        catalog=state.corpus_index,
    )


def get_answer_question_use_case(
    request: Request,
    conversation_repository: Annotated[ConversationRepositoryPort, Depends(get_conversation_repository)],
    document_repository: Annotated[DocumentRepositoryPort, Depends(get_document_repository)],
) -> AnswerQuestionUseCase:
    state = request.app.state
    return AnswerQuestionUseCase(
        conversation_repository=conversation_repository,
        document_repository=document_repository,
        context_retrieval=get_context_retrieval(request),
        verification_port=state.verification_port,
        query_rewriter=QueryRewriter(state.llm_port),
        indexed_chunk_count=state.chroma.count(),
        history_turns=get_app_settings().history_turns,
    )


async def get_current_user(
    auth_port: Annotated[AuthPort, Depends(get_auth_port)],
    user_repository: Annotated[UserRepositoryPort, Depends(get_user_repository)],
    authorization: Annotated[str | None, Header()] = None,
) -> User:
    if authorization is None or not authorization.lower().startswith("bearer "):
        raise UnauthorizedError("Falta el token de sesión")
    user_id: UUID = auth_port.decode_session_token(authorization.split(" ", 1)[1].strip())
    user = await user_repository.get_by_id(user_id)
    if user is None:
        raise UnauthorizedError("La sesión ya no existe")
    return user
