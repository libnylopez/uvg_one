"""Control de consumo de la API de Anthropic: precios, registro de llamadas y presupuesto.

Cada llamada queda en un archivo JSONL (una línea por llamada) con modelo, tokens, costo
estimado, tiempo y tipo de consulta. Nunca se registran claves, prompts ni respuestas.

El presupuesto se comprueba ANTES de cada llamada: costo acumulado + estimación pesimista
de la llamada siguiente (todo el prompt + el máximo de tokens de salida). Si lo supera, la
llamada no se hace.
"""

from __future__ import annotations

import json
import math
import threading
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path

# USD por millón de tokens (entrada, salida). Verificado en
# https://platform.claude.com/docs/en/about-claude/pricing (13/11/2026).
_PRICES: dict[str, tuple[float, float]] = {
    "claude-haiku-5-5": (0.10, 0.50),  # prompts de hasta 100 000 tokens
    "claude-haiku-4-5": (1.00, 5.00),
    "claude-sonnet-5-5": (2.00, 10.00),
    "claude-opus-5-5": (4.00, 20.00),
}
_HAIKU_55_LONG_PROMPT = (0.50, 2.50)  # prompts de más de 100 000 tokens
_LONG_PROMPT_TOKENS = 100_000
# Modelo sin precio conocido: se asume uno caro para que el presupuesto sea conservador.
_UNKNOWN_MODEL = (10.00, 50.00)
# Caracteres por token, a la baja (el español real ronda 3.5–4): sobrestima el costo de entrada.
_CHARS_PER_TOKEN_PESSIMISTIC = 2.5


def prices_for(model: str, input_tokens: int = 0) -> tuple[float, float]:
    if model == "claude-haiku-5-5" and input_tokens > _LONG_PROMPT_TOKENS:
        return _HAIKU_55_LONG_PROMPT
    return _PRICES.get(model, _UNKNOWN_MODEL)


def cost_usd(model: str, input_tokens: int, output_tokens: int) -> float:
    price_in, price_out = prices_for(model, input_tokens)
    return (input_tokens * price_in + output_tokens * price_out) / 1_000_000


def estimate_max_cost(model: str, prompt_chars: int, max_output_tokens: int) -> float:
    """Cota superior del costo de una llamada antes de hacerla."""
    input_tokens = math.ceil(prompt_chars / _CHARS_PER_TOKEN_PESSIMISTIC) + 300  # + sobrecarga del mensaje
    return cost_usd(model, input_tokens, max_output_tokens)


@dataclass(frozen=True, slots=True)
class UsageEntry:
    timestamp: str
    model: str
    purpose: str  # respuesta_verificada | consulta_autosuficiente
    input_tokens: int
    output_tokens: int
    cost_usd: float
    latency_ms: int
    outcome: str  # ok | error:<tipo>


class BudgetExceeded(Exception):
    def __init__(self, spent: float, estimate: float, budget: float) -> None:
        super().__init__(
            f"Presupuesto de API agotado: gastado US${spent:.4f} + próxima llamada hasta US${estimate:.4f} "
            f"supera el límite de US${budget:.2f}"
        )
        self.spent, self.estimate, self.budget = spent, estimate, budget


class UsageLedger:
    def __init__(self, path: str | Path, budget_usd: float) -> None:
        self._path = Path(path)
        self._budget = budget_usd
        self._lock = threading.Lock()
        self._entries: list[UsageEntry] = self._load()

    @property
    def budget_usd(self) -> float:
        return self._budget

    @property
    def spent_usd(self) -> float:
        return sum(entry.cost_usd for entry in self._entries)

    def ensure_within_budget(self, estimated_cost: float) -> None:
        with self._lock:
            spent = self.spent_usd
            if spent + estimated_cost > self._budget:
                raise BudgetExceeded(spent, estimated_cost, self._budget)

    def record(
        self,
        *,
        model: str,
        purpose: str,
        input_tokens: int,
        output_tokens: int,
        latency_ms: int,
        outcome: str = "ok",
    ) -> UsageEntry:
        entry = UsageEntry(
            timestamp=datetime.now(UTC).isoformat(timespec="seconds"),
            model=model,
            purpose=purpose,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            cost_usd=round(cost_usd(model, input_tokens, output_tokens), 8),
            latency_ms=latency_ms,
            outcome=outcome,
        )
        with self._lock:
            self._entries.append(entry)
            self._path.parent.mkdir(parents=True, exist_ok=True)
            with self._path.open("a", encoding="utf-8") as handle:
                handle.write(json.dumps(asdict(entry), ensure_ascii=False) + "\n")
        return entry

    def summary(self) -> dict[str, object]:
        with self._lock:
            entries = list(self._entries)
        by_purpose: dict[str, dict[str, float]] = {}
        for entry in entries:
            bucket = by_purpose.setdefault(entry.purpose, {"calls": 0, "input_tokens": 0, "output_tokens": 0, "cost_usd": 0.0})
            bucket["calls"] += 1
            bucket["input_tokens"] += entry.input_tokens
            bucket["output_tokens"] += entry.output_tokens
            bucket["cost_usd"] = round(bucket["cost_usd"] + entry.cost_usd, 8)
        spent = round(sum(e.cost_usd for e in entries), 8)
        return {
            "budget_usd": self._budget,
            "spent_usd": spent,
            "remaining_usd": round(max(0.0, self._budget - spent), 8),
            "calls": len(entries),
            "failed_calls": sum(1 for e in entries if e.outcome != "ok"),
            "input_tokens": sum(e.input_tokens for e in entries),
            "output_tokens": sum(e.output_tokens for e in entries),
            "by_purpose": by_purpose,
            "last_calls": [asdict(e) for e in entries[-10:]],
        }

    def _load(self) -> list[UsageEntry]:
        if not self._path.exists():
            return []
        entries = []
        for line in self._path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                try:
                    entries.append(UsageEntry(**json.loads(line)))
                except (TypeError, ValueError):
                    continue  # una línea dañada no impide arrancar
        return entries
