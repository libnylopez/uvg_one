from uuid import uuid4

import pytest

from app.application.dto.chat_dto import AnswerQueryRequest, AnswerStatus
from app.application.services.query_rewriter import LocalFollowUpResolver
from app.application.use_cases.answer_question import BUDGET_MESSAGE, AnswerQuestionUseCase
from app.domain.entities.document import Document, DocumentStatus
from app.infrastructure.adapters.llm.single_call_verification_adapter import SingleCallVerificationAdapter
from app.shared.exceptions.domain_errors import (
    LLMBudgetExceededError,
    LLMNotConfiguredError,
    LLMUnavailableError,
)
from app.shared.kernel.clock import utc_now
from tests.fakes import (
    FixedRetrieval,
    InMemoryConversationRepository,
    InMemoryDocumentRepository,
    ScriptedLLM,
    make_passage,
)

GROUNDED = {
    "answer_text": "Necesitas tu título de diversificado.",
    "is_grounded": True,
    "coverage": "complete",
    "cited_fragments": [1],
    "confidence": "high",
    "unsupported_claims": [],
}


async def _setup(llm: ScriptedLLM, passages=True, chunk_count=10, page=2, page_count=3):
    documents = InMemoryDocumentRepository()
    document = Document(uuid4(), "admision.pdf", DocumentStatus.INDEXED, utc_now(), "/x/admision.pdf")
    await documents.add(document)
    found = [make_passage(document.id, "Requisito: título de diversificado.", page=page, page_count=page_count)]
    retrieval = FixedRetrieval(found if passages else [])
    conversations = InMemoryConversationRepository()
    use_case = AnswerQuestionUseCase(
        conversation_repository=conversations,
        document_repository=documents,
        context_retrieval=retrieval,  # type: ignore[arg-type]
        verification_port=SingleCallVerificationAdapter(llm),
        query_rewriter=LocalFollowUpResolver(),
        indexed_chunk_count=chunk_count,
    )
    return use_case, retrieval, conversations, document


# --- A. Conversación local ----------------------------------------------------------------

@pytest.mark.parametrize(
    "message",
    ["Hola", "Buenos días", "¿Cómo estás?", "¿Quién eres?", "Gracias", "Adiós", "¿En qué puedes ayudarme?"],
)
async def test_conversacion_social_no_busca_ni_consume_api(message):
    llm = ScriptedLLM({})
    use_case, retrieval, _, _ = await _setup(llm)
    response = await use_case.execute(AnswerQueryRequest(uuid4(), message))
    assert response.status is AnswerStatus.SMALLTALK
    assert response.sources == () and response.usage.llm_calls == 0
    assert retrieval.queries == [] and llm.calls == []


async def test_respuestas_sociales_varian_en_la_misma_conversacion():
    use_case, _, _, _ = await _setup(ScriptedLLM({}))
    user = uuid4()
    first = await use_case.execute(AnswerQueryRequest(user, "Gracias"))
    second = await use_case.execute(AnswerQueryRequest(user, "Gracias"))
    assert first.answer_text != second.answer_text


async def test_saludo_con_pregunta_se_procesa_como_consulta_institucional():
    llm = ScriptedLLM({"respuesta_verificada": GROUNDED})
    use_case, retrieval, _, _ = await _setup(llm)
    response = await use_case.execute(AnswerQueryRequest(uuid4(), "Hola, ¿cuáles son los requisitos de admisión?"))
    assert response.status is AnswerStatus.ANSWERED
    assert retrieval.queries == ["cuáles son los requisitos de admisión?"]
    assert response.answer_text.startswith("¡Hola!")
    assert response.usage.llm_calls == 1


# --- Respuesta con fuentes, abstención y errores ---------------------------------------------

async def test_respuesta_fundamentada_con_fuentes_y_consumo():
    llm = ScriptedLLM({"respuesta_verificada": GROUNDED})
    use_case, _, conversations, document = await _setup(llm)

    response = await use_case.execute(AnswerQueryRequest(uuid4(), "¿Cuáles son los requisitos de admisión?"))

    assert response.status is AnswerStatus.ANSWERED and response.is_grounded is True
    source = response.sources[0]
    assert (source.document_title, source.page_number, source.document_id) == ("Proceso de Admisión", 2, document.id)
    assert response.usage.llm_calls == 1 and response.usage.input_tokens == 1000
    assert "FRAGMENTOS OFICIALES" in llm.calls[0]["user_prompt"]
    stored = next(iter(conversations.conversations.values())).messages
    assert [m.role.value for m in stored] == ["student", "assistant"]
    assert stored[-1].status == "answered"


async def test_pagina_inexistente_no_se_atribuye():
    use_case, _, _, _ = await _setup(ScriptedLLM({"respuesta_verificada": GROUNDED}), page=9, page_count=3)
    response = await use_case.execute(AnswerQueryRequest(uuid4(), "¿Requisitos de admisión?"))
    assert response.sources[0].page_number is None


async def test_sin_evidencia_se_abstiene_sin_llamar_al_modelo():
    llm = ScriptedLLM({})
    use_case, _, _, _ = await _setup(llm, passages=False)
    response = await use_case.execute(AnswerQueryRequest(uuid4(), "¿Cuál es la capital de Francia?"))
    assert response.status is AnswerStatus.ABSTAINED and response.sources == ()
    assert llm.calls == [] and response.usage.llm_calls == 0


async def test_respuesta_no_fundamentada_se_convierte_en_abstencion():
    llm = ScriptedLLM({"respuesta_verificada": {**GROUNDED, "is_grounded": False, "coverage": "none"}})
    use_case, _, _, _ = await _setup(llm)
    response = await use_case.execute(AnswerQueryRequest(uuid4(), "¿Cuánto cuesta el parqueo?"))
    assert response.status is AnswerStatus.ABSTAINED
    assert "prefiero no darte un dato" in response.answer_text and response.sources == ()


@pytest.mark.parametrize(
    ("error", "fragment"),
    [
        (LLMNotConfiguredError("x"), "API key"),
        (LLMUnavailableError("429"), "no está disponible"),
        (LLMBudgetExceededError("x"), "presupuesto"),
    ],
)
async def test_errores_de_la_api_responden_sin_romper_la_conversacion(error, fragment):
    use_case, _, conversations, _ = await _setup(ScriptedLLM(error=error))
    response = await use_case.execute(AnswerQueryRequest(uuid4(), "¿Cuáles son los requisitos?"))
    assert response.status is AnswerStatus.ERROR and fragment in response.answer_text
    assert len(next(iter(conversations.conversations.values())).messages) == 2


async def test_presupuesto_agotado_usa_mensaje_especifico():
    use_case, _, _, _ = await _setup(ScriptedLLM(error=LLMBudgetExceededError("x")))
    response = await use_case.execute(AnswerQueryRequest(uuid4(), "¿Requisitos?"))
    assert response.answer_text == BUDGET_MESSAGE


async def test_base_de_conocimiento_vacia():
    use_case, _, _, _ = await _setup(ScriptedLLM({}), chunk_count=0)
    response = await use_case.execute(AnswerQueryRequest(uuid4(), "¿Qué carreras hay?"))
    assert response.status is AnswerStatus.NO_DOCUMENTS


# --- C. Seguimiento conversacional (local, sin llamadas extra) ----------------------------

async def test_seguimiento_conserva_el_referente_sin_llamada_extra():
    llm = ScriptedLLM({"respuesta_verificada": GROUNDED})
    use_case, retrieval, _, _ = await _setup(llm)
    user = uuid4()

    await use_case.execute(AnswerQueryRequest(user, "¿Qué información tienes sobre Ingeniería en Informática?"))
    second = await use_case.execute(AnswerQueryRequest(user, "¿Cuánto dura esa carrera?"))
    third = await use_case.execute(AnswerQueryRequest(user, "¿Y cuáles son sus requisitos?"))

    topic = "¿Qué información tienes sobre Ingeniería en Informática?"
    assert retrieval.queries[1] == f"¿Cuánto dura esa carrera? {topic}"
    assert retrieval.queries[2] == f"¿Y cuáles son sus requisitos? {topic}"  # el tema no se encadena
    assert second.intent == third.intent == "seguimiento"
    assert all(call["schema"] == "respuesta_verificada" for call in llm.calls) and len(llm.calls) == 3
    assert "CONVERSACIÓN PREVIA" in llm.calls[-1]["user_prompt"]


async def test_gracias_con_pregunta_conserva_el_seguimiento():
    llm = ScriptedLLM({"respuesta_verificada": GROUNDED})
    use_case, retrieval, _, _ = await _setup(llm)
    user = uuid4()
    await use_case.execute(AnswerQueryRequest(user, "¿Qué es la Licenciatura en Turismo?"))
    response = await use_case.execute(AnswerQueryRequest(user, "Gracias, ¿y cuánto dura la carrera?"))
    assert retrieval.queries[-1].endswith("¿Qué es la Licenciatura en Turismo?")
    assert response.intent == "seguimiento"


async def test_saludo_intermedio_no_borra_el_tema():
    llm = ScriptedLLM({"respuesta_verificada": GROUNDED})
    use_case, retrieval, _, _ = await _setup(llm)
    user = uuid4()
    await use_case.execute(AnswerQueryRequest(user, "¿Qué es la Licenciatura en Turismo?"))
    await use_case.execute(AnswerQueryRequest(user, "gracias"))
    await use_case.execute(AnswerQueryRequest(user, "¿cuánto cuesta?"))
    assert retrieval.queries[-1] == "¿cuánto cuesta? ¿Qué es la Licenciatura en Turismo?"


async def test_pregunta_nueva_cambia_de_tema():
    llm = ScriptedLLM({"respuesta_verificada": GROUNDED})
    use_case, retrieval, _, _ = await _setup(llm)
    user = uuid4()
    await use_case.execute(AnswerQueryRequest(user, "¿Qué es la Licenciatura en Turismo?"))
    await use_case.execute(AnswerQueryRequest(user, "¿Cuándo es la Feria de becas II?"))
    assert retrieval.queries[-1] == "¿Cuándo es la Feria de becas II?"


async def test_pasaje_fusionado_cita_la_pagina_del_fragmento_con_la_respuesta():
    from app.domain.entities.chunk import Chunk, RetrievedChunk
    from app.domain.value_objects.document_facts import DocumentFacts
    from app.domain.value_objects.section_anchor import SectionAnchor
    from app.domain.value_objects.similarity_score import SimilarityScore

    llm = ScriptedLLM({"respuesta_verificada": {**GROUNDED, "answer_text": "Es el **17 de septiembre**."}})
    use_case, retrieval, _, document = await _setup(llm)
    facts = DocumentFacts(title="Calendario Académico", page_count=8)
    august = Chunk(uuid4(), document.id, "17 de agosto: Último día para pagar cuota de agosto", 0,
                   anchor=SectionAnchor(page_start=2, page_end=2), document=facts)
    september = Chunk(uuid4(), document.id, "17 de septiembre: Último día para pagar cuota de septiembre", 1,
                      anchor=SectionAnchor(page_start=3, page_end=3), document=facts)
    merged = RetrievedChunk(
        chunk=Chunk(august.id, document.id, august.text + "\n" + september.text, 0,
                    anchor=SectionAnchor(page_start=2, page_end=3), document=facts),
        score=SimilarityScore(0.7), source_chunk_ids=(august.id, september.id),
    )
    retrieval.passages, retrieval.originals = [merged], [august, september]

    response = await use_case.execute(AnswerQueryRequest(uuid4(), "¿Último día de la cuota de septiembre?"))

    assert (response.sources[0].page_number, response.sources[0].page_end) == (3, None)
