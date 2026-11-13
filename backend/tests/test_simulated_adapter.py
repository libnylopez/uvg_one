from app.domain.entities.chunk import RetrievedChunk
from app.infrastructure.adapters.llm.simulated_llm_adapter import SIMULATION_BANNER, SimulatedLLMAdapter
from app.infrastructure.adapters.llm.single_call_verification_adapter import SingleCallVerificationAdapter
from tests.fakes import make_passage
from uuid import uuid4


async def test_simulacion_marca_la_respuesta_y_cita_el_texto_recuperado_sin_tokens():
    passages: list[RetrievedChunk] = [make_passage(uuid4(), "El costo por nivel es Q500.00 bimestral.")]
    answer = await SingleCallVerificationAdapter(SimulatedLLMAdapter()).answer("¿Cuánto cuesta?", passages)
    assert answer.answer_text.startswith(SIMULATION_BANNER)
    assert "Q500.00" in answer.answer_text
    assert answer.simulated and answer.cited_fragments == (1,)
    assert answer.input_tokens == 0 and answer.cost_usd == 0
