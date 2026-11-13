from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.application.use_cases.start_guest_session import StartGuestSessionUseCase
from app.infrastructure.adapters.persistence.database import get_db_session
from app.infrastructure.entrypoints.api.dependencies import get_start_guest_session_use_case
from app.infrastructure.entrypoints.api.schemas.auth_schemas import AuthResponseSchema

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/guest", response_model=AuthResponseSchema, status_code=201)
async def start_guest_session(
    use_case: Annotated[StartGuestSessionUseCase, Depends(get_start_guest_session_use_case)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> AuthResponseSchema:
    """Modo invitado: sesión temporal sin registro. Cada sesión tiene su propio historial."""
    result = await use_case.execute()
    # Se confirma antes de responder: el cliente usa el token de inmediato.
    await session.commit()
    return AuthResponseSchema.from_session(result)
