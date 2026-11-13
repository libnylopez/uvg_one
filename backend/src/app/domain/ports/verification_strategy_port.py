from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Sequence

from app.domain.entities.chunk import RetrievedChunk
from app.domain.value_objects.verified_answer import VerifiedAnswer


class VerificationStrategyPort(ABC):
    """Produce una respuesta fundamentada en el contexto recuperado, con autoverificación."""

    @abstractmethod
    async def answer(
        self,
        question: str,
        context_chunks: Sequence[RetrievedChunk],
        style_directive: str | None = None,
        conversation: str | None = None,
    ) -> VerifiedAnswer:
        """Responde `question` usando solo `context_chunks` como evidencia.

        `conversation` (opcional) son los turnos previos: sirven para interpretar la
        pregunta, nunca como fuente de datos.
        """
