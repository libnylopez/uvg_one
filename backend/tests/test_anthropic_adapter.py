import json
from types import SimpleNamespace

import anthropic
import httpx
import pytest

from app.infrastructure.adapters.llm.anthropic_llm_adapter import AnthropicLLMAdapter
from app.infrastructure.adapters.llm.single_call_verification_adapter import OUTPUT_SCHEMA
from app.infrastructure.adapters.llm.usage_ledger import UsageLedger
from app.infrastructure.config.settings import AnthropicSettings
from app.shared.exceptions.domain_errors import (
    LLMBudgetExceededError,
    LLMGenerationError,
    LLMNotConfiguredError,
)


class _FakeMessages:
    def __init__(self, response=None, error=None):
        self.response, self.error, self.calls = response, error, []

    async def create(self, **kwargs):
        self.calls.append(kwargs)
        if self.error:
            raise self.error
        return self.response


def _adapter(tmp_path, response=None, error=None, budget=0.5, **settings):
    ledger = UsageLedger(tmp_path / "uso.jsonl", budget_usd=budget)
    adapter = AnthropicLLMAdapter(AnthropicSettings(api_key="sk-test", **settings), ledger)
    messages = _FakeMessages(response, error)
    adapter._client = SimpleNamespace(messages=messages)  # type: ignore[assignment]
    return adapter, messages, ledger


def _response(content, stop_reason="end_turn", input_tokens=3000, output_tokens=400):
    return SimpleNamespace(content=content, stop_reason=stop_reason,
                           usage=SimpleNamespace(input_tokens=input_tokens, output_tokens=output_tokens))


def _ok(payload):
    return _response([SimpleNamespace(type="thinking"), SimpleNamespace(type="text", text=json.dumps(payload))])


async def test_peticion_usa_salida_estructurada_sin_temperature_ni_herramienta_forzada(tmp_path):
    adapter, messages, _ = _adapter(tmp_path, _ok({"answer_text": "ok"}))
    completion = await adapter.complete("sys", "user", OUTPUT_SCHEMA, "respuesta_verificada")

    assert completion.content == {"answer_text": "ok"}
    sent = messages.calls[0]
    assert sent["model"] == "claude-haiku-5-5"
    assert sent["max_tokens"] == 4000
    assert sent["output_config"] == {"effort": "low", "format": {"type": "json_schema", "schema": OUTPUT_SCHEMA}}
    for forbidden in ("temperature", "tool_choice", "tools", "extra_body", "thinking"):
        assert forbidden not in sent


async def test_registra_tokens_y_costo_de_cada_llamada(tmp_path):
    adapter, _, ledger = _adapter(tmp_path, _ok({"a": 1}))
    completion = await adapter.complete("s", "u", OUTPUT_SCHEMA, "respuesta_verificada")
    expected = (3000 * 0.10 + 400 * 0.50) / 1_000_000
    assert completion.cost_usd == pytest.approx(expected)
    assert ledger.spent_usd == pytest.approx(expected)
    assert ledger.summary()["by_purpose"]["respuesta_verificada"]["input_tokens"] == 3000


async def test_sin_presupuesto_no_se_llama_a_la_api(tmp_path):
    adapter, messages, _ = _adapter(tmp_path, _ok({"a": 1}), budget=0.000001)
    with pytest.raises(LLMBudgetExceededError):
        await adapter.complete("s", "u" * 5000, OUTPUT_SCHEMA, "respuesta_verificada")
    assert messages.calls == []


async def test_respuesta_truncada_o_rechazada_es_un_error_explicito(tmp_path):
    adapter, _, _ = _adapter(tmp_path, _response([], stop_reason="max_tokens"))
    with pytest.raises(LLMGenerationError, match="max_tokens"):
        await adapter.complete("s", "u", OUTPUT_SCHEMA, "x")
    adapter, _, _ = _adapter(tmp_path, _response([], stop_reason="refusal"))
    with pytest.raises(LLMGenerationError, match="declinó"):
        await adapter.complete("s", "u", OUTPUT_SCHEMA, "x")


async def test_errores_de_clave_y_saldo_detienen_sin_reintentar(tmp_path):
    request = httpx.Request("POST", "https://api.anthropic.com/v1/messages")
    auth = anthropic.AuthenticationError("bad key", response=httpx.Response(401, request=request), body=None)
    adapter, messages, ledger = _adapter(tmp_path, error=auth)
    with pytest.raises(LLMNotConfiguredError):
        await adapter.complete("s", "u", OUTPUT_SCHEMA, "x")
    assert len(messages.calls) == 1 and ledger.summary()["failed_calls"] == 1

    billing = anthropic.BadRequestError(
        "Your credit balance is too low", response=httpx.Response(400, request=request), body=None
    )
    adapter, _, _ = _adapter(tmp_path, error=billing)
    with pytest.raises(LLMNotConfiguredError, match="saldo"):
        await adapter.complete("s", "u", OUTPUT_SCHEMA, "x")


async def test_sin_api_key_no_llama_a_la_api(tmp_path):
    adapter = AnthropicLLMAdapter(AnthropicSettings(api_key=""), UsageLedger(tmp_path / "u.jsonl", 0.5))
    with pytest.raises(LLMNotConfiguredError):
        await adapter.complete("s", "u", OUTPUT_SCHEMA, "x")


def test_reintentos_acotados_y_clave_fuera_de_la_representacion(tmp_path):
    adapter = AnthropicLLMAdapter(AnthropicSettings(api_key="sk-secreta"), UsageLedger(tmp_path / "u.jsonl", 0.5))
    assert adapter._client.max_retries == 1
    assert "sk-secreta" not in repr(AnthropicSettings(api_key="sk-secreta"))


def test_esquema_de_salida_es_estricto():
    assert OUTPUT_SCHEMA["additionalProperties"] is False
    assert set(OUTPUT_SCHEMA["required"]) == set(OUTPUT_SCHEMA["properties"])
