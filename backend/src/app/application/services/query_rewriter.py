"""Convierte una pregunta de seguimiento en una consulta autosuficiente antes de buscar.

«¿Y cuánto dura?» no recupera nada por sí sola: el buscador necesita saber que se habla de
Ingeniería en Informática. Claude reescribe la pregunta con ayuda de los turnos previos; si
la llamada falla, se usa una regla simple para no bloquear la conversación.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any, Final

from loguru import logger

from app.domain.entities.message import Message, MessageRole
from app.domain.ports.llm_port import LLMPort
from app.shared.exceptions.domain_errors import LLMGenerationError

_SYSTEM_PROMPT: Final = """Ayudas al buscador documental de UVG ONE (Universidad del Valle de \
Guatemala, Campus Altiplano). Recibes una conversación previa y la última pregunta del usuario.

Tu tarea: reescribir la última pregunta como una consulta de búsqueda AUTOSUFICIENTE en español, que \
se entienda sin leer la conversación. Sustituye pronombres y referencias («eso», «esa carrera», \
«¿y los requisitos?») por el tema concreto del que se habla. Conserva nombres propios, carreras, \
documentos, artículos y fechas exactamente como aparecen.

Reglas:
- Si la pregunta ya es autosuficiente o cambia de tema, devuélvela casi igual.
- No respondas la pregunta ni añadas datos que no estén en la conversación.
- is_follow_up=true solo si la pregunta depende de la conversación para entenderse."""

_SCHEMA: Final[dict[str, Any]] = {
    "type": "object",
    "properties": {
        "standalone_query": {"type": "string", "description": "Consulta autosuficiente para buscar."},
        "is_follow_up": {"type": "boolean", "description": "Si dependía de la conversación previa."},
    },
    "required": ["standalone_query", "is_follow_up"],
    "additionalProperties": False,
}

# Por debajo de este número de palabras, una pregunta en medio de una conversación
# casi siempre depende de lo anterior («¿y los costos?»).
_SHORT_QUESTION_WORDS: Final = 6


@dataclass(frozen=True, slots=True)
class RewrittenQuery:
    text: str
    is_follow_up: bool
    method: str  # "none" | "llm" | "heuristic"


def format_history(history: Sequence[Message], max_chars_per_turn: int = 600) -> str:
    """Turnos previos en texto plano, recortados para no inflar el prompt."""
    lines = []
    for message in history:
        speaker = "Usuario" if message.role is MessageRole.STUDENT else "UVG ONE"
        content = " ".join(message.content.split())
        if len(content) > max_chars_per_turn:
            content = content[:max_chars_per_turn].rstrip() + "…"
        lines.append(f"{speaker}: {content}")
    return "\n".join(lines)


class QueryRewriter:
    def __init__(self, llm_port: LLMPort) -> None:
        self._llm_port = llm_port

    async def rewrite(self, question: str, history: Sequence[Message]) -> RewrittenQuery:
        # Solo hay algo que heredar si antes hubo una consulta real (no solo saludos).
        if not any(m.role is MessageRole.ASSISTANT and m.is_grounded is not None for m in history):
            return RewrittenQuery(text=question, is_follow_up=False, method="none")
        try:
            completion = await self._llm_port.complete(
                system_prompt=_SYSTEM_PROMPT,
                user_prompt=f"CONVERSACIÓN PREVIA:\n{format_history(history)}\n\nÚLTIMA PREGUNTA:\n{question}",
                output_schema=_SCHEMA,
                output_schema_name="consulta_autosuficiente",
            )
            text = str(completion.content.get("standalone_query") or "").strip()
            if text:
                return RewrittenQuery(
                    text=text, is_follow_up=bool(completion.content.get("is_follow_up")), method="llm"
                )
        except LLMGenerationError as error:
            logger.warning("No se pudo reescribir la consulta con Claude; se usa la regla simple: {}", error)
        return self._heuristic(question, history)

    @staticmethod
    def _heuristic(question: str, history: Sequence[Message]) -> RewrittenQuery:
        previous = next((m.content for m in reversed(history) if m.role is MessageRole.STUDENT), None)
        if previous and len(question.split()) < _SHORT_QUESTION_WORDS:
            return RewrittenQuery(text=f"{previous} {question}", is_follow_up=True, method="heuristic")
        return RewrittenQuery(text=question, is_follow_up=False, method="heuristic")
