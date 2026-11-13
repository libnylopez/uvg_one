# Cómo levantar UVG ONE en tu computadora

Guía paso a paso para correr el proyecto en local y empezar a trabajar en él.
Tiempo estimado: 20–30 minutos la primera vez (la mayor parte son descargas).

Al terminar tendrás:

- El chat en **http://localhost:5180**
- La API en **http://localhost:8010** (documentación interactiva en http://localhost:8010/docs)

---

## 1. Requisitos

Instala esto antes de empezar:

| Herramienta | Versión | Para qué | Cómo comprobarlo |
|---|---|---|---|
| Git | cualquiera reciente | clonar el repo | `git --version` |
| Docker Desktop | 4.x o superior | base de datos PostgreSQL | `docker --version` (Docker Desktop debe estar **abierto**) |
| Python | **3.12** exactamente (3.13/3.14 no están probados) | backend | `python3.12 --version` |
| Node.js | 20 o 22 | frontend | `node --version` |

En macOS: `brew install python@3.12 node` e instala Docker Desktop desde docker.com.
En Windows: lee primero la sección [Windows](#windows).

También necesitas una **API key de Anthropic** (https://console.anthropic.com → API Keys).
Pídesela a Natán por un canal privado o crea la tuya. **Nunca la subas a GitHub ni la pegues en el chat del grupo.**

---

## 2. Clonar el repositorio

```bash
git clone https://github.com/libnylopez/uvg_one.git
cd uvg_one
```

---

## 3. Crear tu archivo `.env`

El `.env` guarda la configuración y la API key. No está en el repo (a propósito), así que cada quien crea el suyo:

```bash
cp .env.example .env
```

Abre `.env` y cambia estas tres líneas:

```env
ANTHROPIC_API_KEY=sk-ant-...tu-clave...
POSTGRES_PASSWORD=una-clave-cualquiera
SESSION_SECRET=un-texto-largo-aleatorio
```

Para generar valores aleatorios: `python3 -c "import secrets; print(secrets.token_urlsafe(32))"`.

El resto de valores ya vienen bien configurados; no hace falta tocarlos.

---

## 4. Instalar el backend (Python)

```bash
cd backend
python3.12 -m venv .venv
.venv/bin/pip install --upgrade pip
# PyTorch versión CPU primero (evita descargar varios GB de librerías de GPU)
.venv/bin/pip install torch --index-url https://download.pytorch.org/whl/cpu
.venv/bin/pip install -e ".[dev]"
cd ..
```

Comprueba que todo quedó bien corriendo las pruebas:

```bash
cd backend && .venv/bin/pytest -q && cd ..
```

Debe decir `21 passed`.

---

## 5. Instalar el frontend (React)

```bash
cd frontend
npm install
cd ..
```

---

## 6. Levantar todo

Con Docker Desktop abierto:

```bash
./scripts/iniciar.sh
```

El script hace tres cosas:

1. Levanta PostgreSQL en Docker (contenedor `uvg_one-postgres-1`).
2. Arranca el backend en el puerto 8010. **La primera vez** descarga el modelo de embeddings (~470 MB) e indexa los 17 PDF de `documentos_uvg/`. Puede tardar varios minutos; las siguientes veces arranca en segundos.
3. Arranca el frontend en el puerto 5180.

Cuando termine verás `UVG ONE listo: abre http://localhost:5180`.

Para detener todo: `./scripts/detener.sh` (los datos se conservan).

Los logs quedan en `.logs/backend.log` y `.logs/frontend.log`.

---

## 7. Comprobar que funciona

1. Abre http://localhost:5180 y pregunta: **«¿Cuánto cuesta cada nivel del programa de inglés?»**
   Debe responder Q500.00 por nivel (bimestral) y mostrar como fuente *Centro de Idiomas 2025*.
2. Pregunta algo fuera de tema, por ejemplo **«¿Cuál es la capital de Francia?»**. Debe decir que no encontró información (no inventa).
3. Estado del sistema: http://localhost:8010/health debe mostrar `"indexed_chunks": 428` y `"llm_configured": true`.

Prueba completa por terminal (17 preguntas con seguimientos y abstenciones):

```bash
python3 scripts/probar_chat.py < scripts/preguntas_prueba.txt
```

---

## Cómo trabajar en el proyecto

**Antes de empezar cada día:**

```bash
git pull
./scripts/iniciar.sh
```

**Para no pisarnos el trabajo**, usa una rama por tarea:

```bash
git checkout -b mi-tarea        # ej. diseno-interfaz
# ...cambios...
git add -A && git commit -m "Descripción del cambio"
git push -u origin mi-tarea
```

Luego abre un Pull Request en GitHub.

**Dónde está cada cosa:**

| Quiero cambiar… | Archivo(s) |
|---|---|
| La interfaz del chat | `frontend/src/App.tsx`, `frontend/src/components/`, `frontend/src/styles.css` |
| Las preguntas sugeridas de bienvenida | `frontend/src/App.tsx` (constante `SUGGESTIONS`) |
| Cómo habla el agente (prompt de Claude) | `backend/src/app/infrastructure/adapters/llm/single_call_verification_adapter.py` (`SYSTEM_PROMPT`) |
| El flujo del agente (buscar → responder → abstenerse) | `backend/src/app/application/use_cases/answer_question.py` |
| La búsqueda de documentos (RAG) | `backend/src/app/application/services/` |
| El modelo de Claude o parámetros | `.env` (`ANTHROPIC_MODEL`, `ANTHROPIC_EFFORT`) |

**Agregar o cambiar documentos:** copia los PDF a `documentos_uvg/` y ejecuta
`curl -X POST http://localhost:8010/documents/sync` (o reinicia el backend). Se indexan los nuevos,
se reindexan los modificados y se quitan los borrados. Ver estado: http://localhost:8010/documents

**Cambios en el backend:** reinicia con `./scripts/detener.sh && ./scripts/iniciar.sh`.
**Cambios en el frontend:** se ven al instante en el navegador (recarga automática).

---

## Problemas frecuentes

| Síntoma | Solución |
|---|---|
| `Cannot connect to the Docker daemon` | Abre Docker Desktop y espera a que diga *Running*. |
| `El backend se detuvo` al iniciar | Mira `.logs/backend.log`. Lo más común: falta `.env` o `POSTGRES_PASSWORD` cambió después de crear la base (ver fila siguiente). |
| `password authentication failed` | Cambiaste `POSTGRES_PASSWORD` después del primer arranque. Borra la base y se recrea: `docker compose down -v` (borra solo los datos de UVG ONE). |
| `address already in use` en 8010, 5180 o 5442 | Otro programa usa ese puerto. Ciérralo o detén una ejecución anterior con `./scripts/detener.sh`. |
| El chat dice *«falta la API key de Anthropic»* | Revisa `ANTHROPIC_API_KEY` en `.env` y reinicia el backend. |
| El chat dice *«el servicio de IA no está disponible»* | Límite de uso o falla temporal de la API de Anthropic; espera unos segundos. |
| La primera ejecución tarda mucho | Es la descarga del modelo de embeddings (~470 MB) desde Hugging Face. Solo pasa una vez. |
| `pip` falla instalando dependencias | Confirma que usas Python **3.12** (`backend/.venv/bin/python --version`). |

---

## Windows

Los scripts `.sh` necesitan una terminal tipo Unix. Opciones:

- **Recomendado: WSL2** (Ubuntu). Instala Python 3.12 y Node dentro de WSL y sigue esta guía tal cual, con el repo clonado dentro de WSL (`~/uvg_one`, no en `C:\`). Docker Desktop debe tener activada la integración con WSL.
- **Alternativa: Docker completo**, sin instalar Python ni Node: crea el `.env` (paso 3) y ejecuta `docker compose up --build -d`. La primera construcción tarda bastante (descarga PyTorch y el modelo). El chat queda en http://localhost:5180.

---

## Alternativa: todo en Docker

Si prefieres no instalar Python ni Node:

```bash
cp .env.example .env     # y completa los valores (paso 3)
docker compose up --build -d
docker compose logs -f backend   # espera "UVG ONE listo"
```

Detener: `docker compose down`. No uses este modo y `./scripts/iniciar.sh` al mismo tiempo (comparten puertos).

---

Más detalles de arquitectura y endpoints en el [README](README.md).
