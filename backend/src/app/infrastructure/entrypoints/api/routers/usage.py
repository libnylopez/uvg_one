from __future__ import annotations

from fastapi import APIRouter, Request

from app.infrastructure.config.settings import get_anthropic_settings

router = APIRouter(prefix="/usage", tags=["usage"])


@router.get("")
async def usage_summary(request: Request) -> dict[str, object]:
    """Consumo de la API de Anthropic: llamadas, tokens, costo estimado y presupuesto restante.

    No contiene claves, prompts ni respuestas.
    """
    settings = get_anthropic_settings()
    return {"model": settings.model, "mode": settings.mode, **request.app.state.usage_ledger.summary()}
