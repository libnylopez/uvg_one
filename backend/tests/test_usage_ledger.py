import json

import pytest

from app.infrastructure.adapters.llm.usage_ledger import (
    BudgetExceeded,
    UsageLedger,
    cost_usd,
    estimate_max_cost,
    prices_for,
)


def test_precios_de_haiku_55_por_tramo_de_prompt():
    assert prices_for("claude-haiku-5-5") == (0.10, 0.50)
    assert prices_for("claude-haiku-5-5", input_tokens=150_000) == (0.50, 2.50)
    # 50 000 de entrada (tramo normal) + 50 000 de salida
    assert cost_usd("claude-haiku-5-5", 50_000, 50_000) == pytest.approx(0.03)
    # más de 100 000 tokens de entrada: tramo caro
    assert cost_usd("claude-haiku-5-5", 1_000_000, 1_000_000) == pytest.approx(3.00)


def test_modelo_desconocido_usa_precio_conservador():
    assert prices_for("modelo-x") >= prices_for("claude-opus-5-5")


def test_estimacion_previa_es_cota_superior_del_costo_real():
    # Prompt de 12 000 caracteres ≈ 3 400 tokens reales; la estimación asume muchos más y todo el tope de salida.
    estimate = estimate_max_cost("claude-haiku-5-5", 12_000, 4000)
    assert estimate >= cost_usd("claude-haiku-5-5", 3400, 1500)
    assert estimate < 0.01


def test_presupuesto_se_verifica_antes_de_la_llamada(tmp_path):
    ledger = UsageLedger(tmp_path / "uso.jsonl", budget_usd=0.001)
    ledger.ensure_within_budget(0.0009)
    ledger.record(model="claude-haiku-5-5", purpose="x", input_tokens=4000, output_tokens=1000, latency_ms=10)
    with pytest.raises(BudgetExceeded):
        ledger.ensure_within_budget(0.0009)


def test_registro_persiste_y_se_recupera_al_reiniciar_sin_datos_sensibles(tmp_path):
    path = tmp_path / "uso.jsonl"
    ledger = UsageLedger(path, budget_usd=0.5)
    ledger.record(model="claude-haiku-5-5", purpose="respuesta_verificada", input_tokens=3000, output_tokens=500,
                  latency_ms=2100)
    reopened = UsageLedger(path, budget_usd=0.5)
    assert reopened.spent_usd == pytest.approx(cost_usd("claude-haiku-5-5", 3000, 500))
    summary = reopened.summary()
    assert summary["calls"] == 1 and summary["by_purpose"]["respuesta_verificada"]["calls"] == 1
    record = json.loads(path.read_text().splitlines()[0])
    assert set(record) == {"timestamp", "model", "purpose", "input_tokens", "output_tokens", "cost_usd",
                           "latency_ms", "outcome"}
