"""Genera docs/VALIDACION_REAL.md y docs/INFORME_CONSUMO.md a partir de los datos registrados.

Fuentes: evaluacion/resultados_validacion.json y backend/data/usage/anthropic_usage.jsonl.
Uso: python3 evaluacion/generar_informes.py
"""

from __future__ import annotations

import json
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RESULTS = ROOT / "evaluacion" / "resultados_validacion.json"
LEDGER = ROOT / "backend" / "data" / "usage" / "anthropic_usage.jsonl"
CATEGORIES = {"directa": "Directa", "relacional": "Relacional", "seguimiento": "Seguimiento",
              "abstencion": "Abstención", "informal": "Informal / errores ortográficos"}


MANUAL_REVIEW = [
    "## Revisión manual",
    "",
    "Se leyó cada respuesta y se buscaron en el texto de los PDF todos los datos que no son evidentes",
    "(fechas del calendario de noviembre a enero, duraciones, promedios, extensiones y correos).",
    "**No se encontró ningún dato inventado.**",
    "",
    "Problemas detectados en la primera corrida y corregidos (las consultas afectadas se repitieron):",
    "",
    "| Consulta | Problema | Corrección |",
    "|---|---|---|",
    "| V02 | Citaba la pág. 2 del calendario (agosto) para un dato de la pág. 3 | En pasajes fusionados se cita la página del fragmento que contiene la respuesta |",
    "| V10 | «La duración no aparece» y la maestría colada en el contexto | La parte «y cuánto duran» se busca dentro de los folletos encontrados, con sinónimos («años», «total de la carrera») |",
    "| V05 | Dudaba de la duración total de la carrera | Regla en el prompt sobre cómo los folletos indican la duración por etapas |",
    "| V20 | Respondía los requisitos para ser «lead» en lugar de la inscripción | Sinónimos de «qué necesito para inscribirme» (solicitud, documentos, DPI) |",
    "| V19 | La respuesta contenía la palabra «Inglell» (error del propio modelo) | No se reprodujo al repetir la consulta |",
    "",
    "Observaciones que se mantienen:",
    "",
    "- **V10** dice «hay dos ingenierías» y luego menciona una tercera (Agroforestal); los datos de las tres son correctos.",
    "- **V20** describe bien los pasos, pero indica que no aparece la lista de documentos, aunque el proceso",
    "  menciona foto, DPI y certificación de cursos aprobados.",
    "- **V16 y V17** se abstuvieron correctamente, pero usaron una llamada: la búsqueda halló pasajes",
    "  relacionados y fue la verificación de Claude la que determinó que no respaldaban una respuesta.",
    "- Las secciones de los folletos muestran títulos de bloque del PDF poco descriptivos.",
]


def cell(text: str, limit: int | None = None) -> str:
    text = " ".join(str(text).split()).replace("|", "\\|")
    return text if limit is None or len(text) <= limit else text[: limit - 1] + "…"


def validation_report(rows: list[dict]) -> str:
    ok = sum(1 for r in rows if r["ok"])
    by_cat: dict[str, list[int]] = defaultdict(lambda: [0, 0])
    for r in rows:
        by_cat[r["categoria"]][1] += 1
        by_cat[r["categoria"]][0] += bool(r["ok"])
    calls = sum(r["llamadas_claude"] for r in rows)
    cost = sum(r["costo_usd"] for r in rows)
    times = [r["tiempo_s"] for r in rows if r["llamadas_claude"]]
    out = [
        "# Validación real con Claude — UVG ONE",
        "",
        "Modelo `claude-haiku-5-5`. Revisión **determinista** (sin usar a Claude como evaluador):",
        "",
        "- **Fundamentación:** las fuentes citadas están entre los pasajes recuperados, y cada cifra, fecha, monto",
        "  o correo de la respuesta aparece literalmente en esa evidencia.",
        "- **Relevancia:** se cita el documento esperado y la respuesta contiene los datos clave del criterio.",
        "- **Abstención:** la respuesta debe ser `abstained`.",
        "",
        "Además, cada respuesta se **leyó manualmente** y sus datos se contrastaron con el texto de los PDF",
        "(ver «Revisión manual»).",
        "",
        "## Resumen",
        "",
        f"- Consultas: **{len(rows)}** · aprobadas por las comprobaciones: **{ok}/{len(rows)}**",
        f"- Llamadas a Claude: {calls} · costo de esta corrida: **US${cost:.4f}**",
        f"- Tiempo de respuesta (consultas con Claude): promedio {sum(times) / len(times):.1f} s, "
        f"máximo {max(times):.1f} s" if times else "",
        "",
        "| Categoría | Aprobadas |",
        "|---|---|",
        *(f"| {CATEGORIES.get(cat, cat)} | {a}/{t} |" for cat, (a, t) in by_cat.items()),
        "",
        "## Resultados por consulta",
        "",
        "| Id | Categoría | Pregunta | Documento esperado | Estado | Fuentes citadas | Fundamentación | Relevancia | Tiempo | Tokens (ent./sal.) | Costo US$ |",
        "|---|---|---|---|---|---|---|---|---|---|---|",
    ]
    for r in rows:
        out.append(
            f"| {r['id']} | {CATEGORIES.get(r['categoria'], r['categoria'])} | {cell(r['pregunta'])} | "
            f"{cell(r['documento_esperado'])} | {r['status']} | {cell('; '.join(r['fuentes_citadas']) or '—', 160)} | "
            f"{cell(r['fundamentacion'])} | {cell(r['relevancia'])} | {r['tiempo_s']} s | "
            f"{r['tokens_entrada']}/{r['tokens_salida']} | {r['costo_usd']:.5f} |"
        )
    out += ["", *MANUAL_REVIEW, "", "## Respuestas completas", ""]
    for r in rows:
        out += [
            f"### {r['id']} — {r['pregunta']}",
            "",
            f"*Criterio:* {r['criterio']}  ",
            f"*Documentos recuperados:* {', '.join(r['documentos_recuperados']) or '—'}",
            "",
            *("> " + line if line else ">" for line in r["respuesta"].splitlines()),
            "",
        ]
    return "\n".join(out) + "\n"


def consumption_report(entries: list[dict], rows: list[dict]) -> str:
    total = sum(e["cost_usd"] for e in entries)
    tokens_in = sum(e["input_tokens"] for e in entries)
    tokens_out = sum(e["output_tokens"] for e in entries)
    failed = sum(1 for e in entries if e["outcome"] != "ok")
    by_purpose = Counter(e["purpose"] for e in entries)
    final_cost = sum(r["costo_usd"] for r in rows)
    answered = [r for r in rows if r["llamadas_claude"]]
    return "\n".join([
        "# Informe de consumo de la API de Anthropic — UVG ONE",
        "",
        "Generado a partir de `backend/data/usage/anthropic_usage.jsonl` (una línea por llamada; sin claves,",
        "prompts ni respuestas).",
        "",
        "## Configuración",
        "",
        "| Parámetro | Valor |",
        "|---|---|",
        "| Modelo | `claude-haiku-5-5` |",
        "| Precio (prompts ≤ 100 000 tokens) | US$0.10 por millón de tokens de entrada · US$0.50 por millón de salida |",
        "| Fuente del precio | https://platform.claude.com/docs/en/about-claude/pricing (consultado el 13/11/2026) |",
        "| Presupuesto de seguridad | US$0.50 (comprobado antes de cada llamada) |",
        "| Tope de salida por llamada | 4 000 tokens |",
        "| Reintentos automáticos | 1 (clave, saldo o permisos: sin reintento) |",
        "",
        "## Consumo total registrado",
        "",
        "| Concepto | Valor |",
        "|---|---|",
        f"| Llamadas | {len(entries)} ({failed} fallidas) |",
        f"| Tokens de entrada | {tokens_in:,} |".replace(",", " "),
        f"| Tokens de salida (incluye razonamiento interno) | {tokens_out:,} |".replace(",", " "),
        f"| **Costo estimado total** | **US${total:.4f}** ({total / 0.50 * 100:.1f} % del presupuesto) |",
        *(f"| Llamadas `{purpose}` | {count} |" for purpose, count in by_purpose.items()),
        "",
        "El total incluye la corrida de validación y las repeticiones de consultas tras corregir problemas",
        "(V02 tras afinar la página citada; V05, V10, V19 y V20 tras mejorar la recuperación y el prompt).",
        "",
        "## Validación final (20 consultas)",
        "",
        "| Concepto | Valor |",
        "|---|---|",
        f"| Consultas con llamada a Claude | {len(answered)} de {len(rows)} |",
        f"| Costo de la corrida vigente | US${final_cost:.4f} |",
        f"| Costo medio por consulta respondida | US${final_cost / max(1, len(answered)):.5f} |",
        f"| Tokens medios por consulta (entrada / salida) | {sum(r['tokens_entrada'] for r in answered) // max(1, len(answered))} / "
        f"{sum(r['tokens_salida'] for r in answered) // max(1, len(answered))} |",
        "",
        "## Pruebas locales",
        "",
        "0 llamadas: pruebas unitarias con dobles, recuperación sin LLM e integración en modo simulado",
        "(el registro de consumo no cambió durante esas pruebas).",
        "",
        "## Proyección",
        "",
        f"Con el costo medio medido, US$0.50 alcanzan para unas {int(0.50 / max(1e-9, final_cost / max(1, len(answered))))} "
        "consultas respondidas. Saludos y preguntas sin evidencia no consumen tokens.",
        "",
    ])


def main() -> None:
    rows = json.loads(RESULTS.read_text(encoding="utf-8"))["resultados"]
    entries = [json.loads(line) for line in LEDGER.read_text(encoding="utf-8").splitlines() if line.strip()]
    (ROOT / "docs" / "VALIDACION_REAL.md").write_text(validation_report(rows), encoding="utf-8")
    (ROOT / "docs" / "INFORME_CONSUMO.md").write_text(consumption_report(entries, rows), encoding="utf-8")
    print(f"Informes generados: {len(rows)} consultas, {len(entries)} llamadas registradas")


if __name__ == "__main__":
    main()
