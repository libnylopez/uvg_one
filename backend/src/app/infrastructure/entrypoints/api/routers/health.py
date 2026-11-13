from __future__ import annotations

from fastapi import APIRouter, Request

from app.infrastructure.config.settings import get_anthropic_settings

router = APIRouter(tags=["health"])


@router.get("/health")
async def health_check(request: Request) -> dict[str, object]:
    """Estado del servicio (lo usa el healthcheck de Docker y la interfaz)."""
    settings = get_anthropic_settings()
    chroma = getattr(request.app.state, "chroma", None)
    return {
        "status": "ok",
        "indexed_chunks": chroma.count() if chroma else 0,
        "llm_configured": settings.mode == "simulado" or settings.is_configured,
        "llm_model": settings.model,
        "llm_mode": settings.mode,
    }
