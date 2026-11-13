# UVG ONE

Asistente universitario inteligente de la Universidad del Valle de Guatemala, Campus Altiplano.
Responde preguntas en lenguaje natural usando **únicamente** los documentos oficiales que se colocan
en `documentos_uvg/`, muestra las fuentes de cada respuesta y reconoce cuando no tiene información.

Proyecto del curso de Inteligencia Artificial (prototipo funcional, arquitectura RAG).

> **¿Primera vez?** Sigue la guía [CONFIGURACION_LOCAL.md](CONFIGURACION_LOCAL.md) para levantar el proyecto en tu computadora.
>
> Prototipo académico: no es un servicio oficial de la UVG.

## Qué hace

- **Conversa**: saludos, cortesía, identidad y ayuda se resuelven localmente, sin llamar a Claude.
- **Responde con documentos oficiales**: recuperación híbrida sobre 17 PDF y respuesta de Claude verificada contra la evidencia.
- **Muestra fuentes verificables**: documento, sección y página, con un botón para abrir el PDF original en esa página.
- **Mantiene el contexto**: «¿cuánto dura esa carrera?» se entiende por el tema de la conversación (sin llamada extra).
- **Se abstiene** cuando los documentos no respaldan una respuesta.
- **Controla el costo**: registra tokens y costo de cada llamada y bloquea cualquier llamada que supere el presupuesto.

Documentación: [pruebas](docs/INFORME_PRUEBAS.md) · [consumo de API](docs/INFORME_CONSUMO.md) ·
[guía de demostración](docs/GUIA_DEMO.md) · [alcance y limitaciones](docs/LIMITACIONES.md).

## Arquitectura

```
Navegador ── React (Vite, nginx) :5180
   │  HTTP + sesión de invitado (JWT)
   ▼
FastAPI :8010 ───────────────► PostgreSQL (historial, registro de documentos)
   │
   ├─ 1. Clasificación local de la intención → saludo/cortesía/identidad/ayuda: respuesta local (0 tokens)
   ├─ 2. Seguimiento → pregunta + tema vigente, buscada dentro de los documentos del tema (0 tokens)
   ├─ 3. Recuperación híbrida: embeddings multilingües (ChromaDB) + búsqueda léxica (BM25) + fusión RRF
   ├─ 4. Sin evidencia suficiente → abstención (sin llamar al modelo)
   ├─ 5. Control de presupuesto → Claude responde y autoverifica (una llamada, salida JSON con esquema)
   └─ 6. No fundamentada → abstención · Fundamentada → respuesta + fuentes (documento, sección, página, PDF)

Ingesta (al arrancar o con POST /documents/sync):
documentos_uvg/*.pdf → PyMuPDF → limpieza → fragmentos por estructura → embeddings → ChromaDB
```

| Componente | Tecnología |
|---|---|
| Frontend | React 19 + Vite + TypeScript |
| Backend | Python 3.12, FastAPI, arquitectura hexagonal |
| Base vectorial | ChromaDB (persistente, en volumen Docker) |
| Embeddings | `paraphrase-multilingual-MiniLM-L12-v2` (local, gratis) |
| LLM | Claude `claude-haiku-5-5` vía SDK oficial de Anthropic |
| Persistencia | PostgreSQL 16 |
| Despliegue | Docker Compose (proyecto `uvg_one`) |

## Puesta en marcha

### 1. Requisitos

- Docker Desktop en ejecución.
- Una API key de Anthropic (https://console.anthropic.com → API Keys).

### 2. Configurar la API key

El archivo `.env` (en la raíz de `uvg_one/`) ya existe con contraseñas generadas. Ábrelo y pega tu clave:

```
ANTHROPIC_API_KEY=sk-ant-...
```

Si el archivo no existiera: `cp .env.example .env` y completa los valores. El `.env` nunca se sube a git.

### 3. Levantar todo

**Opción rápida (recomendada para desarrollar):** Postgres en Docker, backend y frontend locales.

```bash
./scripts/iniciar.sh     # abre http://localhost:5180
./scripts/detener.sh     # detiene todo (los datos se conservan)
```

Requiere `backend/.venv` instalado (ver «Desarrollo local»). Logs en `.logs/`.

**Opción Docker completa:**

```bash
docker compose up --build -d
```

La primera construcción tarda varios minutos (descarga PyTorch y el modelo de embeddings).
Al arrancar, el backend indexa automáticamente los PDF de `documentos_uvg/`.

| Servicio | URL |
|---|---|
| **Aplicación (chat)** | http://localhost:5180 |
| API (backend) | http://localhost:8010 |
| Documentación interactiva de la API | http://localhost:8010/docs |

Para ver el progreso: `docker compose logs -f backend`. Para detener: `docker compose down`
(los datos se conservan en los volúmenes `uvg_one_postgres_data` y `uvg_one_chroma_data`).

## Documentos institucionales (`documentos_uvg/`)

- Coloca los PDF en `documentos_uvg/` (se admiten subcarpetas).
- Al arrancar, el backend sincroniza la carpeta:
  - PDF **nuevo** → se indexa.
  - PDF **modificado** (detectado por huella SHA-256) → se reindexa.
  - PDF **eliminado** → sus fragmentos se borran del índice.
  - PDF **sin cambios** → no se toca.
- Para sincronizar sin reiniciar: `curl -X POST http://localhost:8010/documents/sync`
- Estado de la base de conocimiento: http://localhost:8010/documents
- Solo se procesan PDF con texto. Los archivos de otro tipo (p. ej. `.xlsx`) se ignoran y se listan
  en `skipped_files`. Un PDF escaneado (solo imagen) queda marcado con error.

## Endpoints principales

| Método | Ruta | Uso |
|---|---|---|
| `POST` | `/auth/guest` | Abre una sesión de invitado (sin registro) |
| `POST` | `/chat` | Envía una pregunta → respuesta, estado y fuentes |
| `GET` | `/chat/history` | Historial de la sesión |
| `GET` | `/documents` | Documentos indexados y su estado |
| `POST` | `/documents/sync` | Re-sincroniza `documentos_uvg/` |
| `GET` | `/documents/{id}/file` | PDF original (solo lectura; admite `#page=N` en el navegador) |
| `GET` | `/search?q=...&topic=...` | Diagnóstico: pasajes que el RAG recuperaría (sin llamar a Claude) |
| `GET` | `/usage` | Consumo de la API: llamadas, tokens, costo estimado y presupuesto restante |
| `GET` | `/health` | Estado del servicio, fragmentos indexados, modo (real/simulado) |

El campo `status` de `/chat` indica el tipo de respuesta: `answered` (con fuentes), `abstained`
(sin evidencia suficiente), `smalltalk`, `no_documents` o `error` (falla de la API o presupuesto agotado).
`usage` indica las llamadas a Claude, los tokens y el costo estimado de esa respuesta.

## Control de costos de la API

| Variable (`.env`) | Por defecto | Efecto |
|---|---|---|
| `ANTHROPIC_MODEL` | `claude-haiku-5-5` | US$0.10 / US$0.50 por millón de tokens de entrada / salida (prompts ≤ 100 000 tokens) |
| `ANTHROPIC_BUDGET_USD` | `0.50` | Antes de cada llamada: gastado + cota pesimista de la llamada ≤ presupuesto; si no, no se llama |
| `ANTHROPIC_MAX_TOKENS` | `4000` | Tope de salida por llamada |
| `ANTHROPIC_MAX_RETRIES` | `1` | Reintentos ante errores transitorios; errores de clave, saldo o permisos no se reintentan |
| `ANTHROPIC_MODE` | `real` | `simulado`: respuestas locales marcadas como SIMULACIÓN (pruebas y demo sin conexión) |
| `REWRITE_MODE` | `local` | `llm`: Claude reescribe los seguimientos (una llamada extra por turno) |

Cada llamada se registra en `backend/data/usage/anthropic_usage.jsonl` (modelo, tokens, costo, tiempo,
tipo; nunca claves, prompts ni respuestas). Resumen en `GET /usage`. Saludos y abstenciones sin
evidencia cuestan 0; una consulta respondida hace **una** llamada.

## Desarrollo local (sin Docker para el backend)

```bash
# Backend
cd backend
python3.12 -m venv .venv
.venv/bin/pip install torch --index-url https://download.pytorch.org/whl/cpu
.venv/bin/pip install -e ".[dev]"
cd ..
docker compose up -d postgres
./scripts/backend_local.sh          # API en http://localhost:8010

# Frontend
cd frontend && npm install && npm run dev   # http://localhost:5180
```

El backend local usa su propio índice en `backend/data/chroma` y la misma base de datos del
contenedor; no ejecutes el backend local y el de Docker al mismo tiempo (ambos usan el puerto 8010).

## Pruebas

```bash
cd backend && .venv/bin/pytest -q                        # 74 pruebas unitarias
cd frontend && npm test                                  # 9 pruebas de componentes y cliente HTTP
./scripts/iniciar.sh --simulado                          # backend sin consumir la API
python3 evaluacion/evaluar_recuperacion.py               # recuperación con 28 preguntas reales
backend/.venv/bin/python evaluacion/prueba_integracion.py  # 49 pruebas HTTP de extremo a extremo
```

Resultados en [docs/INFORME_PRUEBAS.md](docs/INFORME_PRUEBAS.md). La validación con la API real
(`evaluacion/validacion_real.py`) solo se ejecuta con `--autorizado` y respeta el presupuesto.

## Estructura

```
uvg_one/
├── documentos_uvg/          PDF oficiales (fuente de conocimiento)
├── backend/
│   ├── src/app/
│   │   ├── domain/          entidades, puertos y servicios de texto/búsqueda
│   │   ├── application/     casos de uso (answer_question, sync_document_folder) y servicios RAG
│   │   └── infrastructure/  FastAPI, ChromaDB, embeddings, Claude, PostgreSQL, ingesta de PDF
│   ├── migrations/          esquema de base de datos (Alembic)
│   └── tests/
├── frontend/src/            interfaz de chat (React)
├── infrastructure/docker/   Dockerfiles
├── evaluacion/              bancos de preguntas y scripts de evaluación
├── docs/                    informes de pruebas y consumo, guía de demo, limitaciones
├── scripts/                 arranque local y utilidades
└── docker-compose.yml
```

## Origen del código

UVG ONE es un proyecto independiente que reutiliza componentes técnicos de un proyecto anterior del
autor (asistente RAG para UVG Altiplano): el pipeline de ingesta estructural, la recuperación híbrida,
el ensamblado de contexto, la verificación en una sola llamada y la persistencia. Se reescribieron el
caso de uso conversacional, el adaptador de Claude (API actual), la sincronización de documentos,
la configuración y la interfaz. No comparte código en ejecución, base de datos, volúmenes ni
configuración con aquel proyecto.
