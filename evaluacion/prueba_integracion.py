"""Pruebas de integración contra el backend en ejecución, SIN consumir la API de Anthropic.

Requiere el backend en modo simulado:
    ANTHROPIC_MODE=simulado ./scripts/backend_local.sh
Uso (con el Python del backend, que trae PyMuPDF para contar páginas):
    backend/.venv/bin/python evaluacion/prueba_integracion.py
Genera evaluacion/resultados_integracion.json
"""

from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request
import uuid
from pathlib import Path

import pymupdf

BASE = os.environ.get("UVG_ONE_API", "http://127.0.0.1:8010")
HERE = Path(__file__).parent
ROOT = HERE.parent
results: list[dict] = []


def http(method: str, path: str, body=None, token=None, headers=None, raw=False):
    data = json.dumps(body).encode() if body is not None else None
    request = urllib.request.Request(BASE + path, data=data, method=method, headers={
        "Content-Type": "application/json", **({"Authorization": f"Bearer {token}"} if token else {}), **(headers or {})
    })
    try:
        with urllib.request.urlopen(request, timeout=90) as response:
            payload = response.read()
            return response.status, dict(response.headers), payload if raw else json.loads(payload or b"null")
    except urllib.error.HTTPError as error:
        return error.code, dict(error.headers), error.read()


def check(group: str, name: str, ok: bool, detail: str = "") -> None:
    results.append({"grupo": group, "prueba": name, "ok": bool(ok), "detalle": detail})
    print(f"{'OK   ' if ok else 'FALLA'} [{group}] {name}" + (f" — {detail}" if detail and not ok else ""))


def session() -> str:
    return http("POST", "/auth/guest")[2]["session_token"]


def ask(token: str, question: str) -> dict:
    status, _, body = http("POST", "/chat", {"question": question}, token)
    assert status == 200, (status, body)
    return body


def main() -> int:
    health = http("GET", "/health")[2]
    if health.get("llm_mode") != "simulado":
        print("El backend debe correr con ANTHROPIC_MODE=simulado para no consumir tokens.")
        return 2
    spent_before = http("GET", "/usage")[2]["calls"]

    # --- A. Conversación local ----------------------------------------------------------
    token = session()
    for message in ["Hola", "Buenos días", "¿Cómo estás?", "¿Quién eres?", "Gracias", "Adiós",
                    "¿En qué puedes ayudarme?"]:
        r = ask(token, message)
        check("A conversación", f"«{message}» se responde localmente",
              r["status"] == "smalltalk" and r["usage"]["llm_calls"] == 0 and not r["sources"],
              f"status={r['status']} llamadas={r['usage']['llm_calls']}")
    r = ask(session(), "Hola, ¿qué carreras ofrece la UVG?")
    overview = http("GET", "/search?q=" + urllib.parse.quote(r["search_query"] or ""))[2]
    check("A conversación", "«Hola, ¿qué carreras ofrece la UVG?» es consulta institucional (RAG, panorama)",
          r["status"] == "answered" and r["intent"] == "consulta" and r["usage"]["llm_calls"] == 1
          and overview["is_overview"] and len({p["document"] for p in overview["passages"]}) >= 8,
          f"status={r['status']} búsqueda={r['search_query']!r}")

    # --- C. Seguimiento ------------------------------------------------------------------
    token = session()
    first = ask(token, "¿Qué información tienes sobre Ingeniería en Informática?")
    second = ask(token, "¿Cuánto dura esa carrera?")
    third = ask(token, "¿Y cuáles son sus requisitos?")
    topic = "Ingeniería en Informática"
    check("C seguimiento", "1.ª pregunta inicia el tema", first["intent"] == "consulta")
    check("C seguimiento", "«¿Cuánto dura esa carrera?» conserva el referente",
          second["intent"] == "seguimiento" and topic in (second["search_query"] or ""), second["search_query"] or "")
    check("C seguimiento", "«¿Y cuáles son sus requisitos?» conserva el referente",
          third["intent"] == "seguimiento" and topic in (third["search_query"] or ""), third["search_query"] or "")
    informatica = [s for s in second["sources"] if "Informática" in (s.get("document_title") or "")]
    check("C seguimiento", "el seguimiento cita el folleto de Informática", bool(informatica),
          str([s.get("document_title") for s in second["sources"]]))
    history = http("GET", "/chat/history", token=token)[2][0]["messages"]
    check("C seguimiento", "el historial guarda los 6 turnos con su estado",
          len(history) == 6 and history[-1]["status"] == "answered", f"{len(history)} turnos")

    # --- D. Abstención ---------------------------------------------------------------------
    for question in ["¿Cuál es la capital de Francia?", "¿Quién ganó el mundial de 2022?",
                     "¿Cómo preparo un pastel de chocolate?"]:
        r = ask(session(), question)
        check("D abstención", f"«{question}» se abstiene sin llamar al modelo",
              r["status"] == "abstained" and not r["sources"] and r["usage"]["llm_calls"] == 0, r["status"])

    # --- E. Citas -----------------------------------------------------------------------------
    citation_questions = ["¿Cuánto cuesta cada nivel del programa de inglés?",
                          "¿Qué condiciones establece el artículo 18 del reglamento de ayudas financieras?",
                          "¿Cuándo es la Feria de becas II?", "¿Cuánto dura la Licenciatura en Turismo?"]
    for question in citation_questions:
        r = ask(session(), question)
        search = http("GET", "/search?q=" + urllib.parse.quote(question))[2]
        def covered(source):
            page = source.get("page_number")
            return any(p["document"] == source.get("document_title") and
                       (page is None or (p["page"] or 0) <= page <= (p.get("page_end") or p["page"] or 0))
                       for p in search["passages"])
        for source in r["sources"]:
            label = f"{source.get('document_title')} pág. {source.get('page_number')}"
            status, headers, pdf = http("GET", source["document_url"], raw=True)
            ok_pdf = status == 200 and headers.get("content-type", "").startswith("application/pdf") and pdf[:4] == b"%PDF"
            check("E citas", f"{label}: el enlace abre el PDF original", ok_pdf, f"HTTP {status}")
            if ok_pdf and source.get("page_number"):
                pages = pymupdf.open(stream=pdf, filetype="pdf").page_count
                check("E citas", f"{label}: la página existe (de {pages})", 1 <= source["page_number"] <= pages)
            check("E citas", f"{label}: corresponde a un pasaje recuperado (documento y rango de páginas)",
                  covered(source))
            check("E citas", f"{label}: no expone rutas del sistema", "/" not in source["document_name"].split("documentos_uvg")[0]
                  and not source["document_url"].startswith(("/Users", "/app", "file:")))

    # --- F. Errores HTTP ---------------------------------------------------------------------
    check("F errores", "chat sin sesión → 401", http("POST", "/chat", {"question": "hola"})[0] == 401)
    check("F errores", "token inválido → 401", http("POST", "/chat", {"question": "hola"}, "x.y.z")[0] == 401)
    check("F errores", "pregunta vacía → 422", http("POST", "/chat", {"question": ""}, session())[0] == 422)
    check("F errores", "pregunta de más de 2000 caracteres → 422",
          http("POST", "/chat", {"question": "a" * 2001}, session())[0] == 422)
    check("F errores", "documento inexistente → 404", http("GET", f"/documents/{uuid.uuid4()}/file", raw=True)[0] == 404)

    # --- G. Seguridad -----------------------------------------------------------------------------
    for path in ["/documents/..%2F..%2F.env/file", "/documents/../../.env", "/documents/%2e%2e/%2e%2e/etc/passwd/file",
                 "/documents/" + urllib.parse.quote("../../backend/.env") + "/file"]:
        status = http("GET", path, raw=True)[0]
        check("G seguridad", f"path traversal {path} bloqueado", status in (404, 422), f"HTTP {status}")
    some_url = next(iter(http("GET", "/documents")[2]["documents"]))["url"]
    for method in ("POST", "PUT", "DELETE", "PATCH"):
        status = http(method, some_url, body={}, raw=True)[0]
        check("G seguridad", f"{method} sobre un PDF no está permitido", status == 405, f"HTTP {status}")
    exposed = json.dumps([http("GET", p)[2] for p in ("/health", "/usage", "/documents")])
    check("G seguridad", "health/usage/documents no exponen la API key ni rutas absolutas",
          "sk-ant" not in exposed and "/Users/" not in exposed and "/app/" not in exposed)
    log = (ROOT / ".logs" / "backend.log").read_text(encoding="utf-8", errors="ignore")
    check("G seguridad", "el log del backend no contiene la API key", "sk-ant" not in log)
    status, headers, _ = http("OPTIONS", "/chat", headers={"Origin": "https://sitio-ajeno.example",
                                                           "Access-Control-Request-Method": "POST"}, raw=True)
    check("G seguridad", "CORS no autoriza orígenes ajenos", "access-control-allow-origin" not in
          {k.lower() for k in headers}, f"HTTP {status}")

    # --- Costo ------------------------------------------------------------------------------------
    spent_after = http("GET", "/usage")[2]["calls"]
    check("Costo", "ninguna llamada a Anthropic durante estas pruebas", spent_after == spent_before,
          f"{spent_after - spent_before} llamadas")

    passed = sum(r["ok"] for r in results)
    print(f"\nResultado: {passed}/{len(results)} pruebas correctas")
    (HERE / "resultados_integracion.json").write_text(
        json.dumps({"correctas": passed, "total": len(results), "resultados": results}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return 0 if passed == len(results) else 1


if __name__ == "__main__":
    sys.exit(main())
