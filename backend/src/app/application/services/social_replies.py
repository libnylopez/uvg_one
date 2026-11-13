"""Respuestas sociales locales: saludos, cortesía, identidad y ayuda (sin LLM, sin búsqueda).

Cada intención tiene varias formulaciones; se elige según el turno de la conversación para no
repetir la misma frase dos veces seguidas. Nunca llevan fuentes: no afirman nada institucional.
"""

from __future__ import annotations

from app.domain.services.conversational_intent import IntentKind

_TOPICS = (
    "- **Carreras y programas** (licenciaturas, ingenierías, profesorados, maestría)\n"
    "- **Admisión e inscripción** de primer ingreso\n"
    "- **Calendario académico** y fechas importantes\n"
    "- **Ayudas financieras** y reglamento de grupos estudiantiles\n"
    "- **Centro de Idiomas** y cursos de inglés"
)

_REPLIES: dict[IntentKind, tuple[str, ...]] = {
    IntentKind.GREETING: (
        "¡Hola! Soy **UVG ONE**, tu asistente universitario de la UVG Campus Altiplano. "
        "¿En qué puedo ayudarte hoy?",
        "¡Hola de nuevo! ¿Qué te gustaría consultar?",
        "¡Hola! Aquí sigo. Cuéntame qué necesitas saber de la universidad.",
    ),
    IntentKind.WELLBEING: (
        "¡Muy bien, gracias por preguntar! Estoy listo para ayudarte con información de la UVG Altiplano. "
        "¿Qué te gustaría saber?",
        "¡Todo bien por aquí! ¿En qué te ayudo?",
    ),
    IntentKind.IDENTITY: (
        "Soy **UVG ONE**, un asistente inteligente creado como proyecto académico para consultar información "
        "institucional de la Universidad del Valle de Guatemala, Campus Altiplano.\n\n"
        "Respondo usando únicamente los documentos oficiales que tengo cargados (folletos de carreras, "
        "calendario, procesos y reglamentos) y te muestro de qué documento y página sale cada dato. "
        "Si algo no aparece en esos documentos, te lo digo en lugar de inventarlo.",
        "Soy **UVG ONE**, el asistente universitario del proyecto. Busco la respuesta en los documentos "
        "oficiales de la UVG Altiplano y te indico la fuente. ¿Qué quieres consultar?",
    ),
    IntentKind.HELP: (
        "Con gusto te ayudo. Puedo responder preguntas sobre:\n\n" + _TOPICS + "\n\n"
        "Por ejemplo: «¿Cuáles son los pasos para inscribirme?» o «¿Cuánto cuesta el programa de inglés?»",
        "Puedes preguntarme sobre estos temas:\n\n" + _TOPICS,
    ),
    IntentKind.THANKS: (
        "¡Con gusto! Si tienes otra duda sobre la universidad, aquí estoy.",
        "¡De nada! ¿Hay algo más en lo que te pueda ayudar?",
        "Para eso estoy. Cuando quieras, pregúntame otra cosa.",
    ),
    IntentKind.ACKNOWLEDGEMENT: (
        "¡Perfecto! ¿Quieres consultar algo más?",
        "Muy bien. Si te surge otra pregunta, escríbela cuando quieras.",
    ),
    IntentKind.FAREWELL: (
        "¡Hasta pronto! Que te vaya muy bien. Vuelve cuando necesites información de la universidad.",
        "¡Adiós! Fue un gusto ayudarte.",
    ),
    IntentKind.EMPTY: ("Escribe tu pregunta sobre la universidad y con gusto te ayudo.",),
}

_PREFIXES: dict[IntentKind, str] = {
    IntentKind.GREETING: "¡Hola!",
    IntentKind.THANKS: "¡Con gusto!",
    IntentKind.WELLBEING: "¡Muy bien, gracias!",
}


def social_reply(kind: IntentKind, turn: int) -> str:
    """`turn` = cuántas respuestas ya dio el asistente en esta conversación."""
    options = _REPLIES[kind]
    return options[turn % len(options)]


def courtesy_prefix(kind: IntentKind | None) -> str | None:
    """Frase breve para anteponer a una respuesta cuando la consulta venía con saludo o gracias."""
    return _PREFIXES.get(kind) if kind else None
