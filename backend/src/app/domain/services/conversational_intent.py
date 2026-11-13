"""Clasificación local de la intención conversacional (sin LLM, sin búsqueda).

Separa la parte social de un mensaje («hola», «gracias», «perfecto») de la consulta que pueda
traer detrás. Así:

- «Hola»                                   → saludo, se responde localmente.
- «¿Cómo estás?» / «¿Quién eres?»          → social, se responde localmente.
- «Hola, ¿cuáles son los requisitos?»      → consulta institucional (con saludo previo).
- «Gracias, ¿y cuánto dura la carrera?»    → consulta (de seguimiento) con agradecimiento previo.

Todo se evalúa sobre texto plegado (minúsculas, sin tildes) y es determinista.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import Enum

from app.domain.services.spanish_text import fold


class IntentKind(str, Enum):
    GREETING = "saludo"
    FAREWELL = "despedida"
    THANKS = "agradecimiento"
    IDENTITY = "identidad"
    WELLBEING = "cortesia"  # «¿cómo estás?»
    HELP = "ayuda"  # «¿en qué me puedes ayudar?»
    ACKNOWLEDGEMENT = "confirmacion"  # «ok», «entendido»
    EMPTY = "vacio"
    QUERY = "consulta"


@dataclass(frozen=True, slots=True)
class ConversationalIntent:
    kind: IntentKind
    # Texto de la consulta sin la parte social («¿cuáles son los requisitos?»). Vacío si es social.
    query: str = ""
    # Parte social que precedía a la consulta, para responder con naturalidad («¡Hola!»).
    social_prefix: IntentKind | None = None

    @property
    def is_social(self) -> bool:
        return self.kind is not IntentKind.QUERY


_SEP = r"[\s,.;:!¡?¿)(\-–—]*"

# Fórmulas sociales que pueden ir AL INICIO de un mensaje y ser retiradas.
_LEADING = [
    # Las alternativas largas van primero: «buenas tardes» antes que «buenas».
    (IntentKind.GREETING, r"(?:hola+|holi+|hey|buenas tardes|buenas noches|buenos dias|buen dia|buenas|saludos|"
                          r"que tal|que onda|hello|hi)(?:\s+(?:a todos|uvg one|uvg|amigo|asistente))?"),
    (IntentKind.WELLBEING, r"(?:como\s+(?:estas|te va|te encuentras|vas|andas)|como has estado)(?:\s+(?:tu|hoy))?"),
    (IntentKind.THANKS, r"(?:(?:muchas|mil)\s+)?gracias(?:\s+(?:por todo|por la ayuda|por la informacion|uvg one))?"
                        r"|te lo agradezco|muy amable"),
    (IntentKind.ACKNOWLEDGEMENT, r"ok(?:ay|ey)?|vale|perfecto|excelente|genial|listo|entendido|de acuerdo|claro|"
                                 r"muy bien|bien|buenisimo|super"),
    (IntentKind.FAREWELL, r"adios|hasta luego|hasta pronto|nos vemos|bye|chao|chau"),
]

# Mensajes sociales completos (después de retirar fórmulas iniciales).
_WHOLE = [
    (IntentKind.WELLBEING, r"(?:y\s+)?(?:como\s+(?:estas|te va|te encuentras|vas|andas|esta)|que tal estas|"
                           r"como has estado|todo bien)(?:\s+(?:tu|hoy|uvg one))?"),
    (IntentKind.IDENTITY, r"(?:quien|que)\s+(?:eres|sos|es uvg one)|como te llamas|cual es tu nombre|"
                          r"eres (?:un )?(?:robot|bot|humano|una persona|una ia|inteligencia artificial)|"
                          r"como funcionas|de donde sacas (?:la|tu) informacion|"
                          r"(?:que|cual) es (?:uvg one|tu (?:funcion|proposito|objetivo))"),
    (IntentKind.HELP, r"(?:en\s+)?que\s+(?:me\s+)?(?:puedes|podes|sabes)\s+(?:hacer|ayudar(?:me)?|responder)|"
                      r"que\s+puedo\s+preguntar(?:te)?|para que sirves|como me puedes ayudar|"
                      r"(?:necesito\s+)?ayuda|me ayudas|me puedes ayudar|puedes ayudarme|"
                      r"que temas (?:conoces|manejas|sabes)|sobre que (?:temas )?(?:sabes|puedo preguntar)"),
    (IntentKind.FAREWELL, r"(?:eso es todo|es todo|ya no|nada mas)(?:\s+(?:por ahora|por hoy|gracias))?"),
]

_LEADING_RX = [(kind, re.compile(rf"^{_SEP}(?:{pattern})\b{_SEP}")) for kind, pattern in _LEADING]
_WHOLE_RX = [(kind, re.compile(rf"^{_SEP}(?:{pattern}){_SEP}$")) for kind, pattern in _WHOLE]
_TRAILING_FAREWELL = re.compile(rf"{_SEP}(?:adios|hasta luego|hasta pronto|nos vemos|bye|chao){_SEP}$")
_LETTERS = re.compile(r"[a-z0-9ñ]")


def _strip_leading_social(folded: str) -> tuple[str, list[IntentKind]]:
    """Retira fórmulas sociales del inicio, en cualquier orden («hola, muchas gracias, ...»)."""
    found: list[IntentKind] = []
    changed = True
    while changed and folded:
        changed = False
        for kind, rx in _LEADING_RX:
            match = rx.match(folded)
            if match and match.end() > 0:
                folded = folded[match.end():]
                found.append(kind)
                changed = True
                break
    return folded, found


def classify(message: str) -> ConversationalIntent:
    folded = fold(message).strip()
    if not _LETTERS.search(folded):
        return ConversationalIntent(IntentKind.EMPTY)

    rest, leading = _strip_leading_social(folded)
    rest = _TRAILING_FAREWELL.sub("", rest) if leading else rest

    if not _LETTERS.search(rest):
        # Solo fórmulas sociales: manda la más significativa (despedida > gracias > saludo > ok).
        for kind in (
            IntentKind.FAREWELL, IntentKind.THANKS, IntentKind.WELLBEING, IntentKind.GREETING, IntentKind.ACKNOWLEDGEMENT
        ):
            if kind in leading:
                return ConversationalIntent(kind)
        return ConversationalIntent(IntentKind.EMPTY)

    for kind, rx in _WHOLE_RX:
        if rx.match(rest):
            return ConversationalIntent(kind, social_prefix=leading[0] if leading else None)

    # Hay contenido que no es social: es una consulta. Se conserva el texto original sin la parte social.
    query = _original_tail(message, folded_rest=rest)
    return ConversationalIntent(IntentKind.QUERY, query=query, social_prefix=leading[0] if leading else None)


def _original_tail(message: str, folded_rest: str) -> str:
    """Recorta el mensaje original para quedarse con la consulta (respetando tildes y mayúsculas).

    `fold` conserva la longitud carácter a carácter salvo en casos raros; si no coincide, se
    devuelve el mensaje completo, que también es una consulta válida.
    """
    original = message.strip()
    if len(fold(original)) == len(fold(message).strip()):
        tail = original[len(original) - len(folded_rest):].strip()
        if fold(tail) == folded_rest.strip():
            return tail.lstrip(",.;:!¡ ") or original
    return original
