from __future__ import annotations

import sys
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from loguru import logger

from app.infrastructure.adapters.auth.institutional_auth_adapter import InstitutionalAuthAdapter
from app.infrastructure.adapters.document_processing.pymupdf_extractor import (
    PyMuPDFExtractorAdapter,
)
from app.infrastructure.adapters.llm.anthropic_llm_adapter import AnthropicLLMAdapter
from app.infrastructure.adapters.llm.simulated_llm_adapter import SimulatedLLMAdapter
from app.infrastructure.adapters.llm.usage_ledger import UsageLedger
from app.infrastructure.adapters.llm.single_call_verification_adapter import (
    SingleCallVerificationAdapter,
)
from app.infrastructure.adapters.persistence.database import get_engine, get_session_factory
from app.infrastructure.adapters.search.in_memory_corpus_index import InMemoryCorpusIndex
from app.infrastructure.adapters.search.synchronized_vector_store import SynchronizedVectorStore
from app.infrastructure.adapters.vector_store.chroma_vector_store import ChromaVectorStoreAdapter
from app.infrastructure.adapters.vector_store.sentence_transformers_embedding import (
    SentenceTransformersEmbeddingAdapter,
)
from app.infrastructure.bootstrap import sync_documents
from app.infrastructure.config.settings import (
    get_anthropic_settings,
    get_app_settings,
    get_auth_settings,
    get_chroma_settings,
    get_rag_settings,
)
from app.infrastructure.entrypoints.api.middlewares.error_handlers import (
    register_exception_handlers,
)
from app.infrastructure.entrypoints.api.routers import auth, chat, documents, health, search, usage


def _configure_logging() -> None:
    logger.remove()
    logger.add(sys.stderr, level=get_app_settings().log_level, backtrace=False, diagnose=False)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Raíz de composición: crea los adaptadores una vez por proceso y sincroniza los documentos."""
    _configure_logging()
    app_settings = get_app_settings()
    anthropic_settings = get_anthropic_settings()
    rag_settings = get_rag_settings()

    logger.info("Cargando modelo de embeddings {}", rag_settings.embedding_model_name)
    app.state.embedding_port = SentenceTransformersEmbeddingAdapter(model_name=rag_settings.embedding_model_name)
    chroma = ChromaVectorStoreAdapter(
        persist_directory=get_chroma_settings().chroma_persist_dir,
        collection_name=rag_settings.chroma_collection_name,
    )
    app.state.chroma = chroma
    corpus_index = InMemoryCorpusIndex(loader=chroma.iter_chunks, size_probe=chroma.count)
    app.state.corpus_index = corpus_index
    app.state.vector_store_port = SynchronizedVectorStore(chroma, corpus_index)
    app.state.text_extractor_port = PyMuPDFExtractorAdapter()
    app.state.usage_ledger = UsageLedger(anthropic_settings.usage_log_path, anthropic_settings.budget_usd)
    if anthropic_settings.mode == "simulado":
        logger.warning("MODO SIMULACIÓN: las respuestas se arman localmente y NO las genera Claude")
        llm_port = SimulatedLLMAdapter()
    else:
        llm_port = AnthropicLLMAdapter(anthropic_settings, app.state.usage_ledger)
    app.state.llm_port = llm_port
    app.state.verification_port = SingleCallVerificationAdapter(llm_port)
    app.state.auth_port = InstitutionalAuthAdapter(get_auth_settings())

    folder = Path(app_settings.documents_dir).resolve()
    app.state.documents_dir = folder
    async with get_session_factory()() as session:
        app.state.last_sync = await sync_documents(
            session,
            folder,
            chroma,
            app.state.text_extractor_port,
            app.state.embedding_port,
            app.state.vector_store_port,
            rag_settings,
        )
    corpus_index.reload()

    if anthropic_settings.mode == "real" and not anthropic_settings.is_configured:
        logger.warning("ANTHROPIC_API_KEY no está configurada: el chat no podrá generar respuestas")
    logger.info(
        "UVG ONE listo: {} fragmentos indexados, modelo={} ({}), embeddings={}, consumo US${:.4f} de US${:.2f}",
        chroma.count(),
        anthropic_settings.model,
        anthropic_settings.mode,
        rag_settings.embedding_model_name,
        app.state.usage_ledger.spent_usd,
        app.state.usage_ledger.budget_usd,
    )
    yield
    await get_engine().dispose()


def create_app() -> FastAPI:
    app = FastAPI(title="UVG ONE API", version="0.1.0", lifespan=lifespan)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=get_app_settings().cors_origins_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    register_exception_handlers(app)
    app.include_router(health.router)
    app.include_router(auth.router)
    app.include_router(chat.router)
    app.include_router(documents.router)
    app.include_router(search.router)
    app.include_router(usage.router)
    return app


app = create_app()
