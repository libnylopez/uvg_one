import json
from types import SimpleNamespace

import pytest

from app.infrastructure.adapters.llm.anthropic_llm_adapter import AnthropicLLMAdapter
from app.infrastructure.adapters.llm.single_call_verification_adapter import OUTPUT_SCHEMA
from app.infrastructure.config.settings import AnthropicSettings
from app.shared.exceptions.domain_errors import LLMGenerationError, LLMNotConfiguredError


class _FakeMessages:
    def __init__(self, response):
        self.response = response
        self.kwargs = None

    async def create(self, **kwargs):
        self.kwargs = kwargs
        return self.response


def _adapter(response, **settings):
    adapter = AnthropicLLMAdapter(AnthropicSettings(api_key="sk-test", **settings))
    messages = _FakeMessages(response)
    adapter._client = SimpleNamespace(messages=messages)  # type: ignore[assignment]
    return adapter, messages


def _response(content, stop_reason="end_turn"):
    return SimpleNamespace(
        content=content, stop_reason=stop_reason, usage=SimpleNamespace(input_tokens=10, output_tokens=5)
    )


async def test_peticion_usa_salida_estructurada_sin_temperature_ni_herramienta_forzada():
    payload = {"answer_text": "ok"}
    adapter, messages = _adapter(
        _response([SimpleNamespace(type="thinking"), SimpleNamespace(type="text", text=json.dumps(payload))])
    )
    completion = await adapter.complete("sys", "user", OUTPUT_SCHEMA, "respuesta_verificada")

    assert completion.content == payload
    sent = messages.kwargs
    assert sent["model"] == "claude-haiku-5-5"
    assert sent["output_config"]["format"] == {"type": "json_schema", "schema": OUTPUT_SCHEMA}
    assert sent["output_config"]["effort"] == "low"
    for forbidden in ("temperature", "tool_choice", "tools", "extra_body", "thinking"):
        assert forbidden not in sent


async def test_respuesta_truncada_o_rechazada_es_un_error_explicito():
    adapter, _ = _adapter(_response([], stop_reason="max_tokens"))
    with pytest.raises(LLMGenerationError, match="max_tokens"):
        await adapter.complete("s", "u", OUTPUT_SCHEMA, "x")
    adapter, _ = _adapter(_response([], stop_reason="refusal"))
    with pytest.raises(LLMGenerationError, match="declinó"):
        await adapter.complete("s", "u", OUTPUT_SCHEMA, "x")


async def test_sin_api_key_no_llama_a_la_api():
    adapter = AnthropicLLMAdapter(AnthropicSettings(api_key=""))
    with pytest.raises(LLMNotConfiguredError):
        await adapter.complete("s", "u", OUTPUT_SCHEMA, "x")


def test_la_clave_no_aparece_en_la_representacion_de_la_configuracion():
    assert "sk-secreta" not in repr(AnthropicSettings(api_key="sk-secreta"))


def test_esquema_de_salida_es_estricto():
    assert OUTPUT_SCHEMA["additionalProperties"] is False
    assert set(OUTPUT_SCHEMA["required"]) == set(OUTPUT_SCHEMA["properties"])
