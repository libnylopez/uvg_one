import pytest

from app.domain.services.conversational_intent import IntentKind, classify

SOCIAL = [
    ("Hola", IntentKind.GREETING),
    ("Buenos días", IntentKind.GREETING),
    ("buenas noches!", IntentKind.GREETING),
    ("Hola UVG ONE!!", IntentKind.GREETING),
    ("¿Cómo estás?", IntentKind.WELLBEING),
    ("hola, ¿cómo estás?", IntentKind.WELLBEING),
    ("¿Quién eres?", IntentKind.IDENTITY),
    ("¿Eres un robot?", IntentKind.IDENTITY),
    ("¿Cómo funcionas?", IntentKind.IDENTITY),
    ("Gracias", IntentKind.THANKS),
    ("ok gracias", IntentKind.THANKS),
    ("Adiós", IntentKind.FAREWELL),
    ("Muchas gracias, adiós", IntentKind.FAREWELL),
    ("¿En qué puedes ayudarme?", IntentKind.HELP),
    ("ayuda", IntentKind.HELP),
    ("¿Qué puedo preguntarte?", IntentKind.HELP),
    ("perfecto", IntentKind.ACKNOWLEDGEMENT),
    ("?", IntentKind.EMPTY),
]


@pytest.mark.parametrize(("message", "kind"), SOCIAL)
def test_mensajes_sociales_se_resuelven_localmente(message, kind):
    intent = classify(message)
    assert intent.kind is kind and intent.is_social


QUERIES = [
    ("Hola, ¿qué carreras ofrece la UVG?", IntentKind.GREETING, "qué carreras ofrece la UVG?"),
    ("Buenas tardes, quisiera saber los requisitos de admisión", IntentKind.GREETING,
     "quisiera saber los requisitos de admisión"),
    ("Gracias, ¿y cuánto dura la carrera?", IntentKind.THANKS, "y cuánto dura la carrera?"),
    ("¿Cómo estás? ¿Qué carreras hay?", IntentKind.WELLBEING, "Qué carreras hay?"),
    ("Claro, ¿y las becas?", IntentKind.ACKNOWLEDGEMENT, "y las becas?"),
    ("¿Cuál es la capital de Francia?", None, "¿Cuál es la capital de Francia?"),
    ("¿Qué es la UVG?", None, "¿Qué es la UVG?"),
    ("¿y los requisitos?", None, "¿y los requisitos?"),
]


@pytest.mark.parametrize(("message", "prefix", "query"), QUERIES)
def test_consultas_no_se_confunden_con_conversacion_social(message, prefix, query):
    intent = classify(message)
    assert intent.kind is IntentKind.QUERY
    assert intent.social_prefix is prefix
    assert intent.query == query
