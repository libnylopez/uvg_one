"""Prueba de extremo a extremo contra la API de UVG ONE (backend real + Claude real).

Uso:
    python3 scripts/probar_chat.py < scripts/preguntas_prueba.txt
    echo "¿Qué carreras ofrece la UVG Altiplano?" | python3 scripts/probar_chat.py

Cada línea es un turno de conversación; una línea «---» abre una sesión nueva.
Variable opcional UVG_ONE_API (por defecto http://127.0.0.1:8010).
"""
import json, sys, time, urllib.request
import os
BASE = os.environ.get("UVG_ONE_API", "http://127.0.0.1:8010")
def post(path, body=None, token=None):
    req = urllib.request.Request(BASE + path, data=json.dumps(body or {}).encode(), method="POST",
                                 headers={"Content-Type": "application/json", **({"Authorization": f"Bearer {token}"} if token else {})})
    return json.load(urllib.request.urlopen(req, timeout=120))
token = None
for line in sys.stdin:
    q = line.strip()
    if not q: continue
    if q == "---" or token is None:
        token = post("/auth/guest")["session_token"]
        if q == "---": print("\n=== nueva sesión ==="); continue
    t = time.time(); r = post("/chat", {"question": q}, token); dt = time.time() - t
    print(f"\n>>> {q}\n[{r['status']} | confianza={r['confidence']} | {dt:.1f}s | búsqueda: {r['search_query']}]")
    print(r["answer_text"])
    for s in r["sources"]:
        print(f"   · {s.get('document_title') or s['document_name']} — {s.get('section') or ''} pág. {s.get('page_number')}")
