"""Validación con la API REAL de Claude: 20 consultas con control estricto de presupuesto.

NO se ejecuta sin la bandera --autorizado. Requiere el backend en modo real (ANTHROPIC_MODE=real).

    python3 evaluacion/validacion_real.py --autorizado --limite 2      # primera tanda
    python3 evaluacion/validacion_real.py --autorizado --desde V02     # continuar

Protecciones:
- Antes de cada consulta: costo acumulado (GET /usage) + cota pesimista de la consulta ≤ presupuesto.
  (El backend vuelve a comprobarlo antes de cada llamada.)
- Se detiene ante cualquier respuesta con status=error (clave, saldo, cuota, permisos, red).
- Sin reintentos: cada consulta se envía una sola vez.
- No usa a Claude como evaluador: la revisión es determinista contra la evidencia recuperada.

Resultados: evaluacion/resultados_validacion.json (se acumulan entre ejecuciones).
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
import unicodedata
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

BASE = os.environ.get("UVG_ONE_API", "http://127.0.0.1:8010")
HERE = Path(__file__).parent
RESULTS = HERE / "resultados_validacion.json"
# Cota pesimista por llamada con Claude Haiku 5.5: ~4 300 tokens de entrada + 4 000 de salida (tope).
MAX_COST_PER_CALL = (4300 * 0.10 + 4000 * 0.50) / 1_000_000


def fold(text: str) -> str:
    text = unicodedata.normalize("NFKC", text).lower()
    return "".join(c for c in unicodedata.normalize("NFD", text) if unicodedata.category(c) != "Mn")


def http(method: str, path: str, body=None, token=None):
    request = urllib.request.Request(
        BASE + path, method=method, data=json.dumps(body).encode() if body is not None else None,
        headers={"Content-Type": "application/json", **({"Authorization": f"Bearer {token}"} if token else {})},
    )
    with urllib.request.urlopen(request, timeout=120) as response:
        return json.load(response)


_FACT = re.compile(r"[\w.+-]+@[\w-]+\.[\w.]+|Q\s?\d[\d,.]*|\d+(?:[.,]\d+)?")


def facts(text: str) -> set[str]:
    """Cifras, montos y correos de un texto, normalizados («Q500.00» → «500»)."""
    found = set()
    for token in _FACT.findall(text):
        token = token.lower().replace("q", "").replace(" ", "").rstrip(".,")
        token = re.sub(r"[.,]00$", "", token).replace(",", "")
        if token and not re.fullmatch(r"[0-9]", token):  # dígitos sueltos (viñetas, «1.») no son datos
            found.add(token)
    return found


def evaluate(item: dict, response: dict, passages: list[dict], seconds: float) -> dict:
    answer = response["answer_text"]
    # Evidencia = texto de los pasajes + sus títulos y secciones (p. ej. «Turismo 2025»).
    evidence = " ".join(f"{p['document']} {p.get('section') or ''} {p['text']}" for p in passages)
    retrieved_docs = list(dict.fromkeys(p["document"] for p in passages))
    def where(s: dict) -> str:
        page = s.get("page_number")
        span = f"págs. {page}–{s['page_end']}" if s.get("page_end") else f"pág. {page}"
        return f"{s.get('document_title') or s['document_name']} · {s.get('section') or '—'} · {span}"
    sources = [where(s) for s in response["sources"]]
    row = {
        "id": item["id"], "categoria": item["categoria"], "pregunta": item["pregunta"],
        "documento_esperado": item.get("documento", "—"), "criterio": item["criterio"],
        "status": response["status"], "intent": response["intent"], "busqueda": response["search_query"],
        "respuesta": answer, "documentos_recuperados": retrieved_docs, "fuentes_citadas": sources,
        "tiempo_s": round(seconds, 2), "llamadas_claude": response["usage"]["llm_calls"],
        "tokens_entrada": response["usage"]["input_tokens"], "tokens_salida": response["usage"]["output_tokens"],
        "costo_usd": response["usage"]["cost_usd"],
    }
    if item.get("esperado") == "abstained":
        row["fundamentacion"] = "abstención correcta" if response["status"] == "abstained" else "NO se abstuvo"
        row["relevancia"] = "n/a"
        row["ok"] = response["status"] == "abstained"
        return row

    cited_titles = [fold(s.get("document_title") or s["document_name"]) for s in response["sources"]]
    retrieved_folded = [fold(d) for d in retrieved_docs]
    sources_in_evidence = all(t in retrieved_folded for t in cited_titles)
    expected_options = [fold(x) for x in item["documento"].split("|")]
    expected_cited = any(opt in t for opt in expected_options for t in cited_titles)
    answer_facts = facts(answer)
    unsupported = sorted(f for f in answer_facts if f not in fold(evidence).replace(",", ""))
    must = [w for w in item.get("debe_contener", []) if fold(w) not in fold(answer)]
    enough_sources = len({t for t in cited_titles}) >= item.get("min_fuentes", 1)

    row["fundamentacion"] = (
        f"fuentes⊂evidencia={'sí' if sources_in_evidence else 'NO'}; "
        f"cifras verificadas {len(answer_facts) - len(unsupported)}/{len(answer_facts)}"
        + (f" (sin respaldo literal: {', '.join(unsupported)})" if unsupported else "")
    )
    row["relevancia"] = (
        f"documento esperado citado={'sí' if expected_cited else 'NO'}; "
        f"datos clave {'completos' if not must else 'faltan: ' + ', '.join(must)}"
        + ("" if enough_sources else f"; fuentes insuficientes (<{item['min_fuentes']})")
    )
    row["ok"] = (response["status"] == "answered" and sources_in_evidence and expected_cited and not unsupported
                 and not must and enough_sources)
    return row


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--autorizado", action="store_true", help="Confirma que se autorizó consumir créditos")
    parser.add_argument("--limite", type=int, default=None, help="Máximo de consultas en esta ejecución")
    parser.add_argument("--desde", default=None, help="Id desde el que continuar (p. ej. V02)")
    parser.add_argument("--ids", default=None, help="Solo estas consultas, separadas por coma (no seguimientos)")
    args = parser.parse_args()
    if not args.autorizado:
        print("Este script consume créditos de Anthropic. Ejecútalo solo con autorización: --autorizado")
        return 2

    health = http("GET", "/health")
    if health.get("llm_mode") != "real" or not health.get("llm_configured"):
        print(f"El backend no está en modo real con API key configurada: {health}")
        return 2

    items = json.loads((HERE / "validacion_20.json").read_text(encoding="utf-8"))
    previous = json.loads(RESULTS.read_text(encoding="utf-8")) if RESULTS.exists() else {"resultados": []}
    done = {r["id"]: r for r in previous["resultados"]}
    start = next((i for i, it in enumerate(items) if it["id"] == args.desde), 0) if args.desde else 0
    sessions: dict[str, str] = {}
    executed = 0

    selected = items[start:]
    if args.ids:
        wanted = set(args.ids.split(","))
        selected = [it for it in items if it["id"] in wanted and it["categoria"] != "seguimiento"]
    for item in selected:
        if args.limite is not None and executed >= args.limite:
            break
        usage = http("GET", "/usage")
        if usage["spent_usd"] + MAX_COST_PER_CALL > usage["budget_usd"]:
            print(f"Detenido por presupuesto: gastado US${usage['spent_usd']:.4f} de US${usage['budget_usd']:.2f}")
            break
        if item["sesion"] not in sessions:
            sessions[item["sesion"]] = http("POST", "/auth/guest")["session_token"]
            # Un seguimiento necesita su conversación: si se retoma a mitad, se rehace el turno base.
            if item["categoria"] == "seguimiento":
                print(f"{item['id']}: es un seguimiento; ejecuta su conversación desde el inicio (--desde V05).")
                return 1

        started = time.perf_counter()
        response = http("POST", "/chat", {"question": item["pregunta"]}, sessions[item["sesion"]])
        seconds = time.perf_counter() - started
        topic = response.get("topic") if response.get("intent") == "seguimiento" else None
        search = http("GET", "/search?q=" + urllib.parse.quote(response.get("search_query") or item["pregunta"])
                      + (f"&topic={urllib.parse.quote(topic)}" if topic else ""))
        row = evaluate(item, response, search["passages"], seconds)
        done[item["id"]] = row
        executed += 1
        print(f"{'OK   ' if row['ok'] else 'REVISAR'} {row['id']} [{row['categoria']}] {row['status']} · "
              f"{row['tiempo_s']}s · {row['llamadas_claude']} llamada(s) · {row['tokens_entrada']}/{row['tokens_salida']} "
              f"tokens · US${row['costo_usd']:.5f}\n        {row['fundamentacion']} | {row['relevancia']}")
        RESULTS.write_text(json.dumps({"resultados": [done[i["id"]] for i in items if i["id"] in done]},
                                      ensure_ascii=False, indent=2), encoding="utf-8")
        if response["status"] == "error":
            print(f"Detenido: error de la API en {item['id']}: {response['answer_text']}")
            return 1

    usage = http("GET", "/usage")
    print(f"\nConsultas ejecutadas ahora: {executed} · acumulado del proyecto: {usage['calls']} llamadas, "
          f"US${usage['spent_usd']:.4f} de US${usage['budget_usd']:.2f}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
