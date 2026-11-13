from __future__ import annotations

import json
import time
from typing import Any

import anthropic
from loguru import logger

from app.domain.ports.llm_port import LLMPort
from app.domain.value_objects.llm_completion import LLMCompletion
from app.infrastructure.adapters.llm.usage_ledger import BudgetExceeded, UsageLedger, estimate_max_cost
from app.infrastructure.config.settings import AnthropicSettings
from app.shared.exceptions.domain_errors import (
    LLMBudgetExceededError,
    LLMGenerationError,
    LLMNotConfiguredError,
    LLMUnavailableError,
)


class AnthropicLLMAdapter(LLMPort):
    """Llama a Claude con el SDK oficial de Anthropic y obtiene una salida JSON con esquema.

    - Salida estructurada con `output_config.format`, sin `temperature` ni herramienta forzada
      (los modelos actuales, como Claude Haiku 5.5, rechazan ambas cosas).
    - Antes de cada llamada comprueba el presupuesto con una estimación pesimista; después
      registra tokens, costo y tiempo en el libro de consumo.
    - Reintentos del SDK acotados (`max_retries`); errores de clave, permisos o saldo no se reintentan.
    """

    def __init__(self, settings: AnthropicSettings, ledger: UsageLedger) -> None:
        self._client = (
            anthropic.AsyncAnthropic(
                api_key=settings.api_key, timeout=settings.timeout_seconds, max_retries=settings.max_retries
            )
            if settings.is_configured
            else None
        )
        self._model = settings.model
        self._effort = settings.effort
        self._max_tokens = settings.max_tokens
        self._ledger = ledger

    @property
    def model(self) -> str:
        return self._model

    async def complete(
        self,
        system_prompt: str,
        user_prompt: str,
        output_schema: dict[str, Any],
        output_schema_name: str,
        max_tokens: int | None = None,
    ) -> LLMCompletion:
        if self._client is None:
            raise LLMNotConfiguredError("Falta ANTHROPIC_API_KEY en el archivo .env de UVG ONE")

        limit = max_tokens or self._max_tokens
        prompt_chars = len(system_prompt) + len(user_prompt) + len(json.dumps(output_schema))
        estimate = estimate_max_cost(self._model, prompt_chars, limit)
        try:
            self._ledger.ensure_within_budget(estimate)
        except BudgetExceeded as exc:
            logger.error("{}", exc)
            raise LLMBudgetExceededError(str(exc)) from exc

        started_at = time.perf_counter()
        try:
            response = await self._client.messages.create(
                model=self._model,
                max_tokens=limit,
                system=system_prompt,
                messages=[{"role": "user", "content": user_prompt}],
                output_config={
                    "effort": self._effort,
                    "format": {"type": "json_schema", "schema": output_schema},
                },
            )
        except anthropic.APIError as exc:
            self._record_failure(output_schema_name, started_at, exc)
            raise self._translate(exc) from exc

        latency_ms = int((time.perf_counter() - started_at) * 1000)
        entry = self._ledger.record(
            model=self._model,
            purpose=output_schema_name,
            input_tokens=response.usage.input_tokens,
            output_tokens=response.usage.output_tokens,
            latency_ms=latency_ms,
            outcome="ok" if response.stop_reason in ("end_turn", "stop_sequence") else f"error:{response.stop_reason}",
        )
        logger.info(
            "Claude {}: {} ms, tokens entrada={} salida={}, costo≈US${:.5f} (acumulado US${:.4f} de US${:.2f})",
            output_schema_name,
            latency_ms,
            entry.input_tokens,
            entry.output_tokens,
            entry.cost_usd,
            self._ledger.spent_usd,
            self._ledger.budget_usd,
        )

        if response.stop_reason == "refusal":
            raise LLMGenerationError("El modelo declinó responder esta solicitud")
        if response.stop_reason == "max_tokens":
            raise LLMGenerationError(f"La respuesta del modelo se truncó al alcanzar max_tokens={limit}")

        # La respuesta puede empezar con bloques de razonamiento: se busca el bloque de texto.
        text = next((block.text for block in response.content if block.type == "text"), None)
        if text is None:
            raise LLMGenerationError("El modelo no devolvió texto")
        try:
            content = json.loads(text)
        except json.JSONDecodeError as exc:
            raise LLMGenerationError("La salida del modelo no es JSON válido") from exc

        return LLMCompletion(
            content=content,
            input_tokens=entry.input_tokens,
            output_tokens=entry.output_tokens,
            model=self._model,
            cost_usd=entry.cost_usd,
            latency_ms=latency_ms,
        )

    def _record_failure(self, purpose: str, started_at: float, exc: anthropic.APIError) -> None:
        # Una llamada rechazada no consume tokens facturables; se registra para auditoría.
        self._ledger.record(
            model=self._model,
            purpose=purpose,
            input_tokens=0,
            output_tokens=0,
            latency_ms=int((time.perf_counter() - started_at) * 1000),
            outcome=f"error:{type(exc).__name__}",
        )

    def _translate(self, exc: anthropic.APIError) -> LLMGenerationError:
        if isinstance(exc, anthropic.AuthenticationError):
            return LLMNotConfiguredError("La API key de Anthropic fue rechazada (revisa ANTHROPIC_API_KEY)")
        if isinstance(exc, anthropic.PermissionDeniedError):
            return LLMNotConfiguredError(f"La API key no tiene permiso para usar {self._model}")
        if isinstance(exc, anthropic.NotFoundError):
            return LLMNotConfiguredError(f"El modelo '{self._model}' no existe o no está disponible")
        message = str(getattr(exc, "message", exc))
        if isinstance(exc, anthropic.BadRequestError) and "credit" in message.lower():
            return LLMNotConfiguredError("La cuenta de Anthropic no tiene saldo suficiente (billing)")
        if isinstance(exc, (anthropic.RateLimitError, anthropic.APIConnectionError, anthropic.InternalServerError)):
            return LLMUnavailableError(f"El servicio de Claude no está disponible ahora: {type(exc).__name__}")
        status = getattr(exc, "status_code", "?")
        return LLMGenerationError(f"Error de la API de Anthropic ({status}): {message}")
