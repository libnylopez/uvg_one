"""Configuración de UVG ONE, leída solo de variables de entorno (archivo .env del proyecto)."""

from __future__ import annotations

from functools import lru_cache
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class AnthropicSettings(BaseSettings):
    """Variables ANTHROPIC_*. La clave nunca se escribe en logs."""

    model_config = SettingsConfigDict(env_prefix="ANTHROPIC_", extra="ignore")

    # Vacía es válido: el backend arranca, indexa y responde con un error claro al chatear.
    api_key: str = Field(default="", repr=False)
    model: str = "claude-haiku-5-5"
    # real: llama a Claude. simulado: respuestas locales marcadas como SIMULACIÓN (pruebas y demo offline).
    mode: Literal["real", "simulado"] = "real"
    # Profundidad de razonamiento del modelo: low es suficiente para responder sobre documentos.
    effort: Literal["low", "medium", "high"] = "low"
    # Tope de salida por llamada (incluye el razonamiento interno del modelo).
    max_tokens: int = 4000
    timeout_seconds: float = 60.0
    # Reintentos automáticos del SDK ante errores transitorios (nunca ilimitados).
    max_retries: int = 1
    # Presupuesto de seguridad: ninguna llamada se hace si lo gastado + la estimación lo supera.
    budget_usd: float = 0.50
    usage_log_path: str = "./data/usage/anthropic_usage.jsonl"

    @property
    def is_configured(self) -> bool:
        return bool(self.api_key.strip())


class DatabaseSettings(BaseSettings):
    model_config = SettingsConfigDict(extra="ignore")

    database_url: str


class ChromaSettings(BaseSettings):
    model_config = SettingsConfigDict(extra="ignore")

    chroma_persist_dir: str = "./data/chroma"


class AuthSettings(BaseSettings):
    model_config = SettingsConfigDict(extra="ignore")

    session_secret: str = Field(repr=False)
    session_ttl_minutes: int = 60 * 24 * 7
    # Las sesiones de invitado y su historial se eliminan pasado este plazo.
    guest_retention_days: int = 7


class RagSettings(BaseSettings):
    """Parámetros del pipeline RAG (prefijo RAG_)."""

    model_config = SettingsConfigDict(env_prefix="RAG_", extra="ignore")

    top_k: int = 10
    min_similarity_threshold: float = 0.35
    chunk_size: int = 1000
    chunk_overlap: int = 100
    # Multilingüe: el modelo anterior (all-MiniLM-L6-v2) estaba entrenado en inglés.
    embedding_model_name: str = "paraphrase-multilingual-MiniLM-L12-v2"
    chroma_collection_name: str = "uvg_one_documentos"

    chunking_strategy: Literal["fixed", "structural"] = "structural"
    structural_chunk_size: int = 600
    retrieval_mode: Literal["dense", "hybrid"] = "hybrid"
    candidate_pool: int = 30
    min_lexical_coverage: float = 0.5
    rrf_k: int = 60
    evidence_similarity_threshold: float = 0.55
    context_min_lexical_coverage: float = 0.25
    context_char_budget: int = 7000
    section_expansion_limit: int = 1400


class AppSettings(BaseSettings):
    model_config = SettingsConfigDict(extra="ignore")

    app_env: str = "development"
    log_level: str = "INFO"
    cors_origins: str = "http://localhost:5180"
    # Carpeta con los PDF institucionales: la única fuente de conocimiento.
    documents_dir: str = "../documentos_uvg"
    # Cuántos turnos previos se usan para entender preguntas de seguimiento.
    history_turns: int = 6
    # Seguimientos: local (sin costo) o llm (Claude reescribe la pregunta: una llamada extra).
    rewrite_mode: Literal["local", "llm"] = "local"

    @property
    def cors_origins_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]


@lru_cache
def get_anthropic_settings() -> AnthropicSettings:
    return AnthropicSettings()


@lru_cache
def get_database_settings() -> DatabaseSettings:
    return DatabaseSettings()  # type: ignore[call-arg]


@lru_cache
def get_chroma_settings() -> ChromaSettings:
    return ChromaSettings()


@lru_cache
def get_auth_settings() -> AuthSettings:
    return AuthSettings()  # type: ignore[call-arg]


@lru_cache
def get_app_settings() -> AppSettings:
    return AppSettings()


@lru_cache
def get_rag_settings() -> RagSettings:
    return RagSettings()
