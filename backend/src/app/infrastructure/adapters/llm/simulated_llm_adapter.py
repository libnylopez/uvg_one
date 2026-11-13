"""Modelo simulado (ANTHROPIC_MODE=simulado): no llama a ninguna API ni consume tokens.

Sirve para pruebas de extremo a extremo y como respaldo offline en una demostración. Cada
respuesta va marcada como SIMULACIÓN y solo cita literalmente el fragmento recuperado: nunca
debe presentarse como una respuesta generada por Claude.
"""

from __future__ import annotations

import re
from typing import Any

from app.domain.ports.llm_port import LLMPort
from app.domain.value_objects.llm_completion import LLMCompletion

SIMULATION_BANNER = "**[SIMULACIÓN — respuesta armada localmente con el texto recuperado, sin Claude]**"
_FRAGMENT = re.compile(r"^\[(\d+)\] ?(.*)$", re.MULTILINE)
_EXCERPT_CHARS = 420


class SimulatedLLMAdapter(LLMPort):
    model = "simulado"

    async def complete(
        self,
        system_prompt: str,
        user_prompt: str,
        output_schema: dict[str, Any],
        output_schema_name: str,
        max_tokens: int | None = None,
    ) -> LLMCompletion:
        if output_schema_name == "consulta_autosuficiente":
            question = user_prompt.rsplit("ÚLTIMA PREGUNTA:", 1)[-1].strip()
            content: dict[str, Any] = {"standalone_query": question, "is_follow_up": False}
        else:
            content = self._grounded_excerpt(user_prompt)
        return LLMCompletion(content=content, input_tokens=0, output_tokens=0, model=self.model, simulated=True)

    @staticmethod
    def _grounded_excerpt(user_prompt: str) -> dict[str, Any]:
        block = user_prompt.split("FRAGMENTOS OFICIALES:", 1)[-1].split("\n\nPREGUNTA:", 1)[0]
        block = block.split("\n\nCONVERSACIÓN PREVIA:", 1)[0]
        matches = list(_FRAGMENT.finditer(block))
        if not matches:
            return {
                "answer_text": SIMULATION_BANNER, "is_grounded": False, "coverage": "none",
                "cited_fragments": [], "confidence": "low", "unsupported_claims": [],
            }
        first = matches[0]
        end = matches[1].start() if len(matches) > 1 else len(block)
        heading = first.group(2).strip() or "documento oficial"
        text = " ".join(block[first.end():end].split())
        excerpt = text[:_EXCERPT_CHARS].rstrip() + ("…" if len(text) > _EXCERPT_CHARS else "")
        return {
            "answer_text": f"{SIMULATION_BANNER}\n\nEl pasaje más relevante está en **{heading}**:\n\n> {excerpt}",
            "is_grounded": True,
            "coverage": "partial",
            "cited_fragments": [int(first.group(1))],
            "confidence": "low",
            "unsupported_claims": [],
        }
