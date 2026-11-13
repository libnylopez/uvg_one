# Informe de pruebas — UVG ONE

Fecha de ejecución: 13 de noviembre de 2026.
Todas las pruebas de esta sección se ejecutaron **sin llamar a la API de Anthropic** (0 tokens):
usan dobles de prueba, el modo simulado del backend o solo la etapa de recuperación.

## Resumen

| Suite | Qué comprueba | Resultado |
|---|---|---|
| Backend — pruebas unitarias (`pytest`) | clasificador de intención, flujo del agente, seguimientos, presupuesto, adaptador de Claude, PDF seguro, sincronización de documentos | **74 / 74** |
| Frontend — pruebas de componentes (`vitest`) | fuentes y enlace al PDF, abstención, simulación, carga, errores HTTP, tiempo de espera, sesión vencida | **9 / 9** |
| Recuperación con documentos reales (`evaluacion/evaluar_recuperacion.py`) | documento y evidencia correctos en el contexto que recibiría Claude | **27 / 27** |
| Integración backend real en modo simulado (`evaluacion/prueba_integracion.py`) | HTTP de extremo a extremo: conversación, seguimiento, abstención, citas, errores, seguridad | **49 / 49** |

Cómo reproducirlas: ver la sección [Comandos](#comandos).

---

## A. Conversación local (sin API)

Clasificador determinista (`backend/src/app/domain/services/conversational_intent.py`).
26 casos unitarios + 8 casos por HTTP.

| Mensaje | Intención | Llamadas a Claude | Búsqueda |
|---|---|---|---|
| Hola · Buenos días · Hola UVG ONE!! | saludo | 0 | no |
| ¿Cómo estás? | cortesía | 0 | no |
| ¿Quién eres? · ¿Eres un robot? | identidad | 0 | no |
| Gracias · Adiós · Muchas gracias, adiós | agradecimiento / despedida | 0 | no |
| ¿En qué puedes ayudarme? | ayuda | 0 | no |
| **Hola, ¿qué carreras ofrece la UVG?** | **consulta** (con saludo previo) | 1 | sí (panorama) |
| **Gracias, ¿y cuánto dura la carrera?** | **consulta de seguimiento** | 1 | sí |

Las respuestas sociales varían según el turno y nunca llevan fuentes.

## B. Recuperación documental (sin API)

Banco de 28 preguntas construidas con el contenido real de los 17 PDF (`evaluacion/benchmark_recuperacion.json`).
Una pregunta es correcta si el **documento esperado** está en el contexto **y** uno de sus pasajes
contiene el **texto de evidencia** (p. ej. «Q500», «17 de septiembre», «promedio mínimo de 70»).

| Tipo | Correctas |
|---|---|
| Directas | 15 / 15 |
| Relacional (ingenierías y su duración) | 1 / 1 |
| Panorama (¿qué carreras hay?, ≥ 8 documentos) | 1 / 1 |
| Errores ortográficos / lenguaje informal | 2 / 2 |
| Sinónimos («mensualidad» por «cuota», «armar un club») | 2 / 2 |
| Seguimiento (con tema previo) | 3 / 3 |
| Abstención (sin pasajes → sin llamar al modelo) | 3 / 3 |
| **Total** | **27 / 27** |

- Documento correcto en el **primer** pasaje: 22 / 22.
- Contexto promedio enviado a Claude: ≈ 3 600 caracteres (≈ 1 000 tokens).
- La pregunta 28 («¿cuánto cuesta Medicina?») recupera folletos y su abstención depende de la verificación de Claude; se evalúa en la validación real.

**Problemas encontrados y corregidos con este banco** (antes 23/27):

| Problema | Corrección |
|---|---|
| «¿Cuánto dura la maestría?» no recuperaba nada (ningún pasaje superaba el umbral de evidencia) | Si la pregunta nombra un documento y no hay evidencia fuerte, se busca dentro de ese documento |
| «curzo de ingles», «q necesito pa inscribirme en la u» | Vocabulario del dominio ampliado para la corrección ortográfica; abreviaturas informales («pa», «q», «la u») |
| «¿Qué ingenierías hay?» activaba el modo panorama y diluía el contexto entre 13 folletos | El panorama queda solo para preguntas generales («carreras», «programas»); las familias usan la búsqueda normal |
| Seguimiento «¿cuánto dura esa carrera?» recuperaba un artículo del reglamento sobre plazos | El seguimiento se busca dentro de los documentos del tema vigente |

**Umbrales:** se mantuvieron los valores del motor reutilizado (similitud mínima 0.35, evidencia fuerte 0.55,
cobertura léxica 0.5). Con ellos el banco pasa completo y las 3 preguntas fuera de dominio se abstienen,
por lo que no había evidencia para cambiarlos.

## C. Seguimiento conversacional

Resuelto **localmente** (sin llamada extra a Claude): si la pregunta depende del contexto
(«esa carrera», «sus requisitos», «¿y…?», o una pregunta corta sobre un aspecto: duración, costo, horario,
contacto), se busca con la pregunta + el tema vigente y **dentro de los documentos de ese tema**.

| Conversación | Resultado |
|---|---|
| ¿Qué información tienes sobre Ingeniería en Informática? → ¿Cuánto dura esa carrera? → ¿Y cuáles son sus requisitos? | referente conservado en los 3 turnos; el seguimiento cita el folleto de Informática |
| ¿Qué es la Licenciatura en Turismo? → gracias → ¿cuánto cuesta? | un saludo intermedio no borra el tema |
| ¿Qué es la Licenciatura en Turismo? → ¿Cuándo es la Feria de becas II? | cambio de tema detectado |
| ¿Cuánto dura la Licenciatura en Turismo? → modalidad → egresado → más información | los 3 seguimientos citan solo *Turismo 2025* |

El historial guarda cada turno con su estado y su tema (verificado: 6 turnos tras 3 preguntas).

## D. Abstención

| Pregunta | Resultado |
|---|---|
| ¿Cuál es la capital de Francia? | abstención, 0 llamadas a Claude |
| ¿Quién ganó el mundial de 2022? | abstención, 0 llamadas |
| ¿Cómo preparo un pastel de chocolate? | abstención, 0 llamadas |

Si hay pasajes pero Claude marca la respuesta como no fundamentada, el agente también se abstiene
(prueba unitaria `test_respuesta_no_fundamentada_se_convierte_en_abstencion`).

## E. Citas documentales

Para 4 preguntas reales (16 comprobaciones) se verificó, por cada fuente citada:

- el enlace `/documents/{id}/file` devuelve el **PDF original** (HTTP 200, `application/pdf`, cabecera `%PDF`);
- la **página citada existe** en ese PDF (se cuenta con PyMuPDF);
- la fuente corresponde a un **pasaje efectivamente recuperado** (documento y página);
- no se expone ninguna ruta del sistema de archivos.

Una página fuera del rango del documento no se muestra (prueba `test_pagina_inexistente_no_se_atribuye`).
El enlace usa `#page=N`, que respetan los visores de Chrome, Edge y Firefox; donde no se respete, el
botón muestra el número de página para ubicarla a mano.

## F. Frontend y backend

| Prueba | Resultado |
|---|---|
| chat sin sesión / token inválido | 401 |
| pregunta vacía / de más de 2 000 caracteres | 422 |
| documento inexistente | 404 |
| error del servidor, sin conexión, tiempo de espera agotado (frontend) | mensaje claro, la interfaz no se bloquea |
| sesión de invitado vencida (frontend) | se abre otra y se reintenta **una** vez |
| errores de Claude (clave, saldo, cuota, presupuesto) | respuesta `status=error` con mensaje específico; la conversación sigue |

## G. Seguridad básica

| Prueba | Resultado |
|---|---|
| Path traversal (`../`, `%2e%2e`, rutas absolutas, enlaces simbólicos) | bloqueado (404/422) |
| POST / PUT / DELETE / PATCH sobre un PDF | 405 (solo lectura) |
| `/health`, `/usage`, `/documents` | no exponen la API key ni rutas absolutas |
| log del backend | no contiene la API key |
| CORS desde un origen ajeno | no autorizado |
| Instrucciones dentro de los PDF | el prompt las trata como contenido, no como órdenes |

## Costo de estas pruebas

El libro de consumo (`GET /usage`) no registró **ninguna** llamada durante las pruebas locales.

---

## Validación real con Claude (autorizada el 13/11/2026)

20 consultas con `claude-haiku-5-5`: **20/20 aprobadas** por las comprobaciones deterministas
(fuentes dentro de la evidencia, cifras verificadas literalmente, documento esperado citado, datos clave
presentes, abstenciones correctas) y revisadas manualmente contra los PDF: no se encontraron datos inventados.

| Categoría | Aprobadas |
|---|---|
| Directas | 8/8 |
| Relacionales | 4/4 |
| Seguimiento | 3/3 |
| Abstención | 3/3 |
| Informal / errores ortográficos | 2/2 |

Costo de la corrida vigente: US$0.0121; total de la API en todo el proyecto: US$0.0160 (26 llamadas).
Detalle por consulta y respuestas completas: [VALIDACION_REAL.md](VALIDACION_REAL.md).
Consumo: [INFORME_CONSUMO.md](INFORME_CONSUMO.md).

Problemas que la lectura de las respuestas reales destapó y se corrigieron: página citada en pasajes
fusionados (V02), duración de las ingenierías (V10), duración por etapas (V05), lenguaje informal sobre
inscripción (V20). Tras cada corrección se repitieron las suites locales (sin tokens) y solo las
consultas afectadas con la API.

---

## Comandos

```bash
# Unitarias
cd backend && .venv/bin/pytest -q
cd frontend && npm test

# Backend en modo simulado (no consume tokens)
./scripts/iniciar.sh --simulado

# Recuperación con documentos reales y pruebas de integración
python3 evaluacion/evaluar_recuperacion.py
backend/.venv/bin/python evaluacion/prueba_integracion.py
```
