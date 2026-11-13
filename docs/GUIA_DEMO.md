# Guía de demostración — UVG ONE

Duración sugerida: 8–10 minutos. Costo estimado de la demo completa con Claude Haiku 5.5: menos de US$0.01.

## Antes de presentar (15 minutos antes)

```bash
cd uvg_one
./scripts/iniciar.sh
```

Comprueba:

| Qué | Cómo | Esperado |
|---|---|---|
| Backend | http://localhost:8010/health | `"status":"ok"`, `"indexed_chunks": 428`, `"llm_mode":"real"`, `"llm_configured": true` |
| Documentos | http://localhost:8010/documents | 17 documentos con estado `indexed` |
| Presupuesto | http://localhost:8010/usage | `remaining_usd` mayor que 0 |
| Interfaz | http://localhost:5180 | pantalla de bienvenida con preguntas sugeridas |
| Un PDF | en la demo, botón «Ver documento» | se abre el PDF en la página citada |

Usa **Chrome, Edge o Firefox** (Safari puede ignorar el salto a la página del PDF).
Para empezar con una conversación limpia, pulsa **Nueva conversación**.

## Guion

Todas las preguntas de este guion se probaron con la API real el 13/11/2026 (ver [VALIDACION_REAL.md](VALIDACION_REAL.md)).

### 1. Conversación natural (sin costo)

| Escribe | Qué mostrar |
|---|---|
| Hola | responde al instante; no busca en documentos ni usa la API |
| ¿Quién eres? | se presenta y explica que solo usa documentos oficiales |
| ¿En qué puedes ayudarme? | lista los temas que conoce |

> Punto a explicar: los mensajes sociales se clasifican localmente, sin llamar a Claude.

### 2. Consulta con fuentes verificables

| Escribe | Qué mostrar |
|---|---|
| ¿Cuánto cuesta cada nivel del programa de inglés? | Q500.00 por nivel (bimestral); fuente *Centro de Idiomas 2025* |
| (pulsa **Ver documento**) | se abre el folleto original en la página citada |
| ¿Cuál es el último día para pagar la cuota de septiembre sin recargo? | 17 de septiembre; fuente *Calendario Académico* |

> Punto a explicar: recuperación híbrida (semántica + léxica) → Claude responde solo con esos pasajes y verifica cada afirmación.

### 3. Seguimiento conversacional

| Escribe | Qué mostrar |
|---|---|
| ¿Cuánto dura la Licenciatura en Turismo? | 5 años (técnico + licenciatura) |
| ¿En qué modalidad se imparte esa carrera? | entiende «esa carrera» = Turismo |
| ¿Dónde pido más información? | correo y teléfono del folleto de Turismo |

### 4. Panorama y lenguaje informal

| Escribe | Qué mostrar |
|---|---|
| Hola, ¿qué carreras ofrece la UVG Altiplano? | saluda y lista los programas de varios folletos |
| q necesito pa inscribirme en la u | entiende lenguaje informal: pasos de inscripción |

### 5. Honestidad: cuando no sabe

| Escribe | Qué mostrar |
|---|---|
| ¿Cuál es la capital de Francia? | dice que no tiene esa información (sin llamar a la API) |
| ¿Cuánto cuesta la carrera de Medicina? | reconoce que no aparece en los documentos; no inventa un precio |

### 6. Cierre técnico (opcional)

- http://localhost:8010/usage → llamadas, tokens y costo de la demo.
- http://localhost:8010/docs → API documentada.
- `docs/INFORME_PRUEBAS.md` → pruebas automatizadas y resultados.

## Si falla la conexión a Anthropic: demostración offline

```bash
./scripts/detener.sh
./scripts/iniciar.sh --simulado
```

La interfaz muestra un aviso permanente **MODO SIMULACIÓN** y cada respuesta lleva la etiqueta
«Simulación · respuesta armada localmente, no generada por Claude». En este modo:

- la conversación social, la búsqueda en documentos, las fuentes y los PDF funcionan igual;
- las respuestas institucionales son un **extracto literal** del pasaje recuperado, no una redacción de Claude.

**Explícalo así a la audiencia.** Nunca presentes una respuesta simulada como generada en tiempo real.

## Si algo no responde

| Síntoma | Acción |
|---|---|
| La interfaz dice «No hay conexión con el servidor» | `./scripts/detener.sh && ./scripts/iniciar.sh`; revisar `.logs/backend.log` |
| «Se alcanzó el presupuesto de uso de la API» | subir `ANTHROPIC_BUDGET_USD` en `.env` y reiniciar, o pasar a modo simulado |
| «El servicio de inteligencia artificial no está disponible» | esperar unos segundos y repetir; si persiste, modo simulado |
