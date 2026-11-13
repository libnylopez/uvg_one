from __future__ import annotations

import json
import time
from typing import Any

import anthropic
from loguru import logger

from app.domain.ports.llm_port import LLMPort
from app.domain.value_objects.llm_completion import LLMCompletion
from app.infrastructure.config.settings import AnthropicSettings
from app.shared.exceptions.domain_errors import (
    LLMGenerationError,
    LLMNotConfiguredError,
    LLMUnavailableError,
)


class AnthropicLLMAdapter(LLMPort):
    """Llama a Claude con el SDK oficial de Anthropic y obtiene una salida JSON con esquema.

    Usa salidas estructuradas (`output_config.format`) en lugar de forzar una herramienta, y
    no envía `temperature`: los modelos actuales (p. ej. Claude Haiku 5.5) rechazan ambas
    cosas. La profundidad del razonamiento se controla con `output_config.effort`.
    """

    def __init__(self, settings: AnthropicSettings) -> None:
        self._configured = settings.is_configured
        self._client = (
            anthropic.AsyncAnthropic(api_key=settings.api_key, timeout=settings.timeout_seconds)
            if self._configured
            else None
        )
        self._model = settings.model
        self._effort = settings.effort
        self._max_tokens = settings.max_tokens

    @property
    def model(self) -> str:
        return self._model

    async def complete(
        self,
        system_prompt: str,
        user_prompt: str,
        output_schema: dict[str, Any],
        output_schema_name: str,
    ) -> LLMCompletion:
        if self._client is None:
            raise LLMNotConfiguredError(
                "Falta ANTHROPIC_API_KEY en el archivo .env de UVG ONE"
            )

        started_at = time.perf_counter()
        try:
            response = await self._client.messages.create(
                model=self._model,
                max_tokens=self._max_tokens,
                system=system_prompt,
                messages=[{"role": "user", "content": user_prompt}],
                output_config={
                    "effort": self._effort,
                    "format": {"type": "json_schema", "schema": output_schema},
                },
            )
        except anthropic.AuthenticationError as exc:
            raise LLMNotConfiguredError("La API key de Anthropic fue rechazada (revisa ANTHROPIC_API_KEY)") from exc
        except anthropic.PermissionDeniedError as exc:
            raise LLMNotConfiguredError(f"La API key no tiene permiso para usar {self._model}") from exc
        except anthropic.NotFoundError as exc:
            raise LLMNotConfiguredError(f"El modelo '{self._model}' no existe o no está disponible") from exc
        except (anthropic.RateLimitError, anthropic.APIConnectionError, anthropic.InternalServerError) as exc:
            raise LLMUnavailableError(f"El servicio de Claude no está disponible ahora: {type(exc).__name__}") from exc
        except anthropic.APIStatusError as exc:
            raise LLMGenerationError(f"Error de la API de Anthropic ({exc.status_code}): {exc.message}") from exc

        elapsed_ms = (time.perf_counter() - started_at) * 1000
        if response.stop_reason == "refusal":
            raise LLMGenerationError("El modelo declinó responder esta solicitud")
        if response.stop_reason == "max_tokens":
            raise LLMGenerationError(
                f"La respuesta del modelo se truncó al alcanzar max_tokens={self._max_tokens}"
            )

        # La respuesta puede empezar con bloques de razonamiento: se busca el bloque de texto.
        text = next((block.text for block in response.content if block.type == "text"), None)
        if text is None:
            raise LLMGenerationError("El modelo no devolvió texto")
        try:
            content = json.loads(text)
        except json.JSONDecodeError as exc:
            raise LLMGenerationError("La salida del modelo no es JSON válido") from exc

        logger.info(
            "Claude respondió en {:.0f}ms ({}: modelo={}, tokens entrada={}, salida={})",
            elapsed_ms,
            output_schema_name,
            self._model,
            response.usage.input_tokens,
            response.usage.output_tokens,
        )
        return LLMCompletion(
            content=content,
            input_tokens=response.usage.input_tokens,
            output_tokens=response.usage.output_tokens,
            model=self._model,
        )
