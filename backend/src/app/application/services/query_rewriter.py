"""Preguntas de seguimiento: convertir «¿y cuánto dura?» en una consulta que el buscador entienda.

Dos estrategias, elegibles por configuración (`REWRITE_MODE`):

- **local** (por defecto, sin costo): si la pregunta depende de la conversación (pronombres como
  «esa carrera» o «sus requisitos», o una pregunta corta sin tema propio), se busca con la
  pregunta más el *tema* de la conversación, guardado en el turno anterior.
- **llm**: Claude reescribe la pregunta como consulta autosuficiente (una llamada extra por turno).

En ambos casos, Claude recibe después la conversación previa para interpretar la pregunta al
redactar la respuesta, así que el referente no se pierde.
"""

from __future__ import annotations

import re
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from typing import Any, Final

from loguru import logger

from app.domain.entities.message import Message, MessageRole
from app.domain.ports.llm_port import LLMPort
from app.domain.services.query_analyzer import QueryAnalyzer
from app.domain.services.spanish_text import content_words, fold
from app.domain.value_objects.document_outline import DocumentOutline
from app.domain.value_objects.llm_completion import LLMCompletion
from app.shared.exceptions.domain_errors import LLMGenerationError, LLMNotConfiguredError


@dataclass(frozen=True, slots=True)
class RewrittenQuery:
    text: str  # lo que se busca
    is_follow_up: bool
    method: str  # "none" | "local" | "llm" | "heuristic"
    topic: str  # tema de la conversación tras este turno (se guarda para el siguiente)
    completion: LLMCompletion | None = None  # consumo de la llamada, si la hubo


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


def last_topic(history: Sequence[Message]) -> str | None:
    """Tema vigente: el de la última respuesta que trató una consulta (no un saludo)."""
    for message in reversed(history):
        if message.role is MessageRole.ASSISTANT and message.topic_query:
            return message.topic_query
    return None


# --- Estrategia local ------------------------------------------------------------------------

# Se evalúa sobre minúsculas CON tildes: «está» (verbo) no es «esta» (demostrativo).
_ANAPHORA = re.compile(
    r"^\W*(?:y|e|pero|entonces|tambien|también|además|ademas|o sea)\b"
    r"|\b(?:eso|esto|aquello|ello|ésa|ése|ésta|éste)\b"
    r"|\b(?:esa|ese|esta|este|esas|esos|estas|estos|dicha|dicho|dichas|dichos|la misma|el mismo)\s+\w+"
    r"|\b(?:sus|su)\s+(?:requisitos|costos?|precios?|duraci[oó]n|horarios?|pensum|pénsum|cursos|materias|"
    r"fechas?|beneficios|requerimientos|modalidad|contacto|correo|tel[eé]fono|ventajas|perfil|campo)\b"
    r"|\b(?:de ahí|de ahi|ahí|allí|ahi|alli)\b"
)
# Palabras que nombran un tema propio: una pregunta que las trae inicia su propio tema.
_TOPIC_NOUNS = frozenset(
    fold(word)
    for word in (
        "carrera carreras licenciatura licenciaturas ingeniería ingenierías profesorado profesorados maestría "
        "maestrías técnico programa programas admisión admisiones inscripción inscribirme inscribir calendario "
        "fechas feria becas beca ayuda ayudas financiera financieras crédito reglamento grupos grupo clubes club "
        "asociación idiomas inglés turismo informática sistemas administración empresas agroforestal agroforestería "
        "agrícola pecuaria alimentos industrial industrialización educación física itec bachillerato básico "
        "matrícula cuota cuotas pago pagos parqueo biblioteca residencias examen suficiencia graduación rector"
    ).split()
)
# Aspectos que se preguntan de un tema ya nombrado: «¿cuánto dura?», «¿y el horario?».
_ASPECT_WORDS = frozenset(
    fold(word)
    for word in (
        "dura duran duración duracion años cuesta cuestan costo costos precio precios pagar requisitos requisito "
        "requiere necesito horario horarios cuándo cuando dónde donde contacto correo teléfono telefono "
        "extensión modalidad virtual presencial pénsum pensum cursos materias fechas fecha inicia empieza "
        "termina plazo pasos documentos inscribo inscribirse beneficios perfil trabajar trabaja egresado "
        "egresados salidas laboral ubicación ubicacion niveles nivel cupos título titulo"
    ).split()
)
_SHORT_QUESTION_WORDS: Final = 6


class LocalFollowUpResolver:
    """Resuelve seguimientos sin llamar al modelo."""

    def __init__(self, outlines: Callable[[], Sequence[DocumentOutline]] | None = None) -> None:
        self._outlines = outlines or (lambda: ())

    async def rewrite(self, question: str, history: Sequence[Message]) -> RewrittenQuery:
        topic = last_topic(history)
        if not topic or not self.depends_on_context(question):
            return RewrittenQuery(text=question, is_follow_up=False, method="none", topic=question)
        return RewrittenQuery(text=f"{question} {topic}", is_follow_up=True, method="local", topic=topic)

    def depends_on_context(self, question: str) -> bool:
        if _ANAPHORA.search(question.lower()):
            return True
        if QueryAnalyzer.analyze(question, self._outlines()).target_documents:
            return False  # nombra un documento: es un tema nuevo
        if any(fold(word) in _TOPIC_NOUNS for word in re.findall(r"\w+", question)):
            return False
        words = {fold(word) for word in re.findall(r"\w+", question)}
        return len(content_words(question)) <= _SHORT_QUESTION_WORDS and bool(words & _ASPECT_WORDS)


# --- Estrategia con Claude (opcional) --------------------------------------------------------

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


class QueryRewriter:
    """Reescritura con Claude. Si la llamada falla, se usa la estrategia local."""

    def __init__(self, llm_port: LLMPort, fallback: LocalFollowUpResolver | None = None) -> None:
        self._llm_port = llm_port
        self._fallback = fallback or LocalFollowUpResolver()

    async def rewrite(self, question: str, history: Sequence[Message]) -> RewrittenQuery:
        topic = last_topic(history)
        if not topic:
            return RewrittenQuery(text=question, is_follow_up=False, method="none", topic=question)
        try:
            completion = await self._llm_port.complete(
                system_prompt=_SYSTEM_PROMPT,
                user_prompt=f"CONVERSACIÓN PREVIA:\n{format_history(history)}\n\nÚLTIMA PREGUNTA:\n{question}",
                output_schema=_SCHEMA,
                output_schema_name="consulta_autosuficiente",
                max_tokens=1000,
            )
            text = str(completion.content.get("standalone_query") or "").strip()
            if text:
                follow_up = bool(completion.content.get("is_follow_up"))
                return RewrittenQuery(
                    text=text, is_follow_up=follow_up, method="llm",
                    topic=topic if follow_up else question, completion=completion,
                )
        except LLMNotConfiguredError:
            pass  # sin clave o sin presupuesto: se resuelve localmente
        except LLMGenerationError as error:
            logger.warning("No se pudo reescribir la consulta con Claude; se usa la estrategia local: {}", error)
        return await self._fallback.rewrite(question, history)
