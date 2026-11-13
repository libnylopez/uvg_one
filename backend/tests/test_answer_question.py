from uuid import uuid4

from app.application.dto.chat_dto import AnswerQueryRequest, AnswerStatus
from app.application.services.query_rewriter import QueryRewriter
from app.application.use_cases.answer_question import AnswerQuestionUseCase
from app.domain.entities.document import Document, DocumentStatus
from app.infrastructure.adapters.llm.single_call_verification_adapter import SingleCallVerificationAdapter
from app.shared.exceptions.domain_errors import LLMNotConfiguredError, LLMUnavailableError
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


async def _setup(llm: ScriptedLLM, passages=True, chunk_count=10):
    documents = InMemoryDocumentRepository()
    document = Document(uuid4(), "admision.pdf", DocumentStatus.INDEXED, utc_now(), "/x/admision.pdf")
    await documents.add(document)
    retrieval = FixedRetrieval([make_passage(document.id, "Requisito: título de diversificado.")] if passages else [])
    conversations = InMemoryConversationRepository()
    use_case = AnswerQuestionUseCase(
        conversation_repository=conversations,
        document_repository=documents,
        context_retrieval=retrieval,  # type: ignore[arg-type]
        verification_port=SingleCallVerificationAdapter(llm),
        query_rewriter=QueryRewriter(llm),
        indexed_chunk_count=chunk_count,
    )
    return use_case, retrieval, conversations


async def test_respuesta_fundamentada_con_fuentes_citadas():
    llm = ScriptedLLM({"respuesta_verificada": GROUNDED})
    use_case, _, conversations = await _setup(llm)

    response = await use_case.execute(AnswerQueryRequest(uuid4(), "¿Cuáles son los requisitos de admisión?"))

    assert response.status is AnswerStatus.ANSWERED
    assert response.is_grounded is True
    assert [s.document_title for s in response.sources] == ["Proceso de Admisión"]
    assert response.sources[0].page_number == 2
    assert "FRAGMENTOS OFICIALES" in llm.calls[0]["user_prompt"]
    stored = next(iter(conversations.conversations.values())).messages
    assert [m.role.value for m in stored] == ["student", "assistant"]


async def test_sin_evidencia_se_abstiene_sin_llamar_al_modelo():
    llm = ScriptedLLM({})
    use_case, _, _ = await _setup(llm, passages=False)
    response = await use_case.execute(AnswerQueryRequest(uuid4(), "¿Cuál es la capital de Francia?"))
    assert response.status is AnswerStatus.ABSTAINED
    assert response.sources == ()
    assert llm.calls == []


async def test_respuesta_no_fundamentada_se_convierte_en_abstencion():
    llm = ScriptedLLM({"respuesta_verificada": {**GROUNDED, "is_grounded": False, "coverage": "none"}})
    use_case, _, _ = await _setup(llm)
    response = await use_case.execute(AnswerQueryRequest(uuid4(), "¿Cuánto cuesta el parqueo?"))
    assert response.status is AnswerStatus.ABSTAINED
    assert "prefiero no darte un dato" in response.answer_text
    assert response.sources == ()


async def test_seguimiento_se_reescribe_antes_de_buscar():
    llm = ScriptedLLM(
        {
            "respuesta_verificada": GROUNDED,
            "consulta_autosuficiente": {"standalone_query": "requisitos de la carrera de Turismo", "is_follow_up": True},
        }
    )
    use_case, retrieval, _ = await _setup(llm)
    user = uuid4()
    await use_case.execute(AnswerQueryRequest(user, "¿Qué es la carrera de Turismo?"))
    response = await use_case.execute(AnswerQueryRequest(user, "¿y los requisitos?"))

    assert retrieval.queries[-1] == "requisitos de la carrera de Turismo"
    assert response.search_query == "requisitos de la carrera de Turismo"
    last_prompt = llm.calls[-1]["user_prompt"]
    assert "CONVERSACIÓN PREVIA" in last_prompt and "Turismo" in last_prompt


async def test_saludo_se_responde_sin_buscar_ni_llamar_al_modelo():
    llm = ScriptedLLM({})
    use_case, retrieval, _ = await _setup(llm)
    response = await use_case.execute(AnswerQueryRequest(uuid4(), "Hola!"))
    assert response.status is AnswerStatus.SMALLTALK
    assert retrieval.queries == [] and llm.calls == []


async def test_base_de_conocimiento_vacia():
    use_case, _, _ = await _setup(ScriptedLLM({}), chunk_count=0)
    response = await use_case.execute(AnswerQueryRequest(uuid4(), "¿Qué carreras hay?"))
    assert response.status is AnswerStatus.NO_DOCUMENTS


async def test_sin_api_key_responde_con_aviso_claro():
    use_case, _, _ = await _setup(ScriptedLLM(error=LLMNotConfiguredError("falta clave")))
    response = await use_case.execute(AnswerQueryRequest(uuid4(), "¿Cuáles son los requisitos?"))
    assert response.status is AnswerStatus.ERROR
    assert "API key" in response.answer_text


async def test_api_no_disponible_no_rompe_la_conversacion():
    use_case, _, conversations = await _setup(ScriptedLLM(error=LLMUnavailableError("429")))
    response = await use_case.execute(AnswerQueryRequest(uuid4(), "¿Cuáles son los requisitos?"))
    assert response.status is AnswerStatus.ERROR
    assert "no está disponible" in response.answer_text
    assert len(next(iter(conversations.conversations.values())).messages) == 2
