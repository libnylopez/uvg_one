"""Evaluación de la recuperación RAG con preguntas reales, SIN llamar a Claude (0 tokens).

Usa GET /search, que devuelve exactamente los pasajes que recibiría el modelo.
Uso:  python3 evaluacion/evaluar_recuperacion.py   (con el backend en http://127.0.0.1:8010)
Genera evaluacion/resultados_recuperacion.json
"""

import json
import os
import sys
import unicodedata
import urllib.parse
import urllib.request
from pathlib import Path

BASE = os.environ.get("UVG_ONE_API", "http://127.0.0.1:8010")
HERE = Path(__file__).parent


def fold(text: str) -> str:
    text = unicodedata.normalize("NFKC", text).lower()
    return "".join(c for c in unicodedata.normalize("NFD", text) if unicodedata.category(c) != "Mn")


def search(query: str, topic: str | None = None) -> dict:
    extra = f"&topic={urllib.parse.quote(topic)}" if topic else ""
    with urllib.request.urlopen(f"{BASE}/search?q={urllib.parse.quote(query)}{extra}", timeout=60) as response:
        return json.load(response)


def evaluate(item: dict) -> dict:
    # Seguimiento: misma consulta que arma el resolvedor local (pregunta + tema de la conversación).
    query = f"{item['pregunta']} {item['tema']}" if item.get("tema") else item["pregunta"]
    result = search(query, item.get("tema"))
    passages = result["passages"]
    documents = [p["document"] for p in passages]
    row = {
        "id": item["id"], "tipo": item["tipo"], "pregunta": item["pregunta"], "consulta": query,
        "pasajes": len(passages), "caracteres_contexto": sum(len(p["text"]) for p in passages),
        "documentos": list(dict.fromkeys(documents)),
        "primer_pasaje": f"{passages[0]['document']} · {passages[0]['section'] or '—'} · pág. {passages[0]['page']}"
        if passages else None,
    }
    if item["tipo"] == "abstencion":
        row["ok"] = not passages
        row["criterio"] = "sin pasajes (abstención antes de llamar al modelo)"
    elif item["tipo"] == "abstencion_llm":
        row["ok"] = None
        row["criterio"] = item.get("nota", "")
    elif item.get("documentos_requeridos"):
        missing = [d for d in item["documentos_requeridos"] if not any(fold(d) in fold(x) for x in documents)]
        row["faltantes"] = missing
        row["ok"] = not missing
        row["criterio"] = "todos estos documentos en el contexto: " + ", ".join(item["documentos_requeridos"])
    elif item["tipo"] == "panorama":
        row["ok"] = len(set(documents)) >= item["min_documentos"]
        row["criterio"] = f"al menos {item['min_documentos']} documentos distintos"
    else:
        wanted = fold(item["documento"])
        doc_ranks = [i for i, d in enumerate(documents) if wanted in fold(d)]
        evidence = fold(item["evidencia"])
        evidence_ranks = [i for i, p in enumerate(passages) if wanted in fold(p["document"]) and evidence in fold(p["text"])]
        row.update(
            documento_esperado=item["documento"], evidencia_esperada=item["evidencia"],
            documento_encontrado=bool(doc_ranks), documento_top1=bool(doc_ranks) and doc_ranks[0] == 0,
            evidencia_encontrada=bool(evidence_ranks),
            evidencia_rango=evidence_ranks[0] + 1 if evidence_ranks else None,
        )
        row["ok"] = row["documento_encontrado"] and row["evidencia_encontrada"]
        row["criterio"] = "documento esperado en el contexto Y el texto de evidencia en uno de sus pasajes"
    return row


def main() -> int:
    items = json.loads((HERE / "benchmark_recuperacion.json").read_text(encoding="utf-8"))
    rows = [evaluate(item) for item in items]
    for row in rows:
        mark = {True: "OK  ", False: "FALLA", None: "n/a "}[row["ok"]]
        extra = f"evidencia en pasaje #{row.get('evidencia_rango')}" if row.get("evidencia_rango") else ""
        print(f"{mark} {row['id']} [{row['tipo']:14}] {row['pasajes']:2} pasajes {row['caracteres_contexto']:5} car. "
              f"| {row['pregunta'][:62]:62} {extra}")
        if row["ok"] is False:
            print(f"       documentos: {row['documentos']}")
    measured = [r for r in rows if r["ok"] is not None]
    passed = sum(1 for r in measured if r["ok"])
    answerable = [r for r in rows if "documento_top1" in r]
    summary = {
        "preguntas": len(rows), "evaluadas": len(measured), "correctas": passed,
        "documento_top1": sum(1 for r in answerable if r["documento_top1"]), "con_documento_esperado": len(answerable),
        "caracteres_contexto_promedio": round(sum(r["caracteres_contexto"] for r in rows if r["pasajes"]) /
                                              max(1, sum(1 for r in rows if r["pasajes"]))),
    }
    print(f"\nResultado: {passed}/{len(measured)} correctas · documento correcto en primer lugar "
          f"{summary['documento_top1']}/{summary['con_documento_esperado']} · contexto promedio "
          f"{summary['caracteres_contexto_promedio']} caracteres")
    (HERE / "resultados_recuperacion.json").write_text(
        json.dumps({"resumen": summary, "resultados": rows}, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return 0 if passed == len(measured) else 1


if __name__ == "__main__":
    sys.exit(main())
