# UVG ONE

Asistente universitario inteligente de la Universidad del Valle de Guatemala, Campus Altiplano.
Responde preguntas en lenguaje natural usando **únicamente** los documentos oficiales que se colocan
en `documentos_uvg/`, muestra las fuentes de cada respuesta y reconoce cuando no tiene información.

Proyecto del curso de Inteligencia Artificial (prototipo funcional, arquitectura RAG).

> **¿Primera vez?** Sigue la guía [CONFIGURACION_LOCAL.md](CONFIGURACION_LOCAL.md) para levantar el proyecto en tu computadora.

## Arquitectura

```
Navegador ── React (Vite, nginx) :5180
   │  HTTP + sesión de invitado (JWT)
   ▼
FastAPI :8010 ───────────────► PostgreSQL (historial, registro de documentos)
   │
   ├─ 1. Saludo/presentación → respuesta local (sin IA)
   ├─ 2. Pregunta de seguimiento → Claude la reescribe como consulta autosuficiente
   ├─ 3. Recuperación híbrida: embeddings multilingües (ChromaDB) + búsqueda léxica (BM25) + fusión RRF
   ├─ 4. Sin evidencia suficiente → abstención (sin llamar al modelo)
   ├─ 5. Claude responde y autoverifica cada afirmación (una llamada, salida JSON con esquema)
   └─ 6. No fundamentada → abstención · Fundamentada → respuesta + fuentes citadas

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
| `GET` | `/search?q=...` | Diagnóstico: pasajes que el RAG recuperaría (sin llamar a Claude) |
| `GET` | `/health` | Estado del servicio, fragmentos indexados, si Claude está configurado |

El campo `status` de `/chat` indica el tipo de respuesta: `answered` (con fuentes), `abstained`
(sin evidencia suficiente), `smalltalk`, `no_documents` o `error` (falla de la API de Claude).

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
cd backend && .venv/bin/pytest -q      # sincronización, flujo del agente, adaptador de Claude
cd frontend && npm test                # componentes de mensaje y fuentes
```

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
├── scripts/                 utilidades de desarrollo
└── docker-compose.yml
```

## Origen del código

UVG ONE es un proyecto independiente que reutiliza componentes técnicos de un proyecto anterior del
autor (asistente RAG para UVG Altiplano): el pipeline de ingesta estructural, la recuperación híbrida,
el ensamblado de contexto, la verificación en una sola llamada y la persistencia. Se reescribieron el
caso de uso conversacional, el adaptador de Claude (API actual), la sincronización de documentos,
la configuración y la interfaz. No comparte código en ejecución, base de datos, volúmenes ni
configuración con aquel proyecto.
