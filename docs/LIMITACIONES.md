# Alcance y limitaciones — UVG ONE

UVG ONE es un **prototipo académico** del curso de Inteligencia Artificial. No es un servicio oficial
de la Universidad del Valle de Guatemala ni está aprobado por ella.

## Qué puede responder

Solo lo que aparece en los 17 PDF de `documentos_uvg/`:

| Tema | Documentos |
|---|---|
| Carreras y programas | 13 folletos 2025: Administración de Empresas, Agroforestería, Agrícola y Pecuaria, Educación Física, Facultad de Educación, Industrialización de Alimentos, Informática, Tecnología Industrial, Turismo, Maestría, ITEC, Centro de Idiomas y Bifoliar General |
| Admisión e inscripción | Proceso de Admisión e Inscripción de Estudiante de Primer Ingreso |
| Fechas | Calendario Académico V3 (**agosto 2026 – enero 2027**) |
| Normativa | Reglamento de ayudas financieras (v10.0) y Reglamento de grupos estudiantiles (v2) |

Además conversa localmente (saludos, cortesía, identidad, ayuda) y mantiene el contexto de preguntas de seguimiento.

## Qué no puede hacer

- **Responder con información que no esté en esos PDF.** Si un dato no aparece (costos de matrícula de
  las carreras, autoridades, otros campus, otro período del calendario), se abstiene.
- Consultar sistemas institucionales: notas, pagos, Moodle, reservas o trámites en línea.
- Leer PDF escaneados (solo imagen): quedan marcados con error al indexar. Tampoco procesa `.xlsx`
  (el calendario 2025 en Excel de la carpeta se ignora).
- Garantizar que la información esté vigente: depende de la versión de cada documento.

## Limitaciones técnicas conocidas

- **Tablas:** algunas tablas de los PDF pierden su estructura al extraer el texto (p. ej. la matriz del
  Artículo 18 del reglamento de ayudas financieras). El prompt pide no atribuir filas a programas cuando
  la tabla no se conserva.
- **Secciones de los folletos:** los folletos no tienen artículos ni capítulos; algunas citas muestran
  títulos de bloque poco descriptivos tomados del propio PDF («Develop your potencial in», «Proyectos y prácticas»).
- **Navegación a página:** `#page=N` funciona en Chrome, Edge y Firefox; Safari puede abrir el PDF en la
  primera página. El botón indica siempre el número de página citada.
- **Seguimientos:** se resuelven con reglas locales (pronombres, preguntas cortas sobre un aspecto). Un
  seguimiento muy implícito puede tratarse como pregunta nueva; reformularla con el tema lo resuelve.
  Existe un modo opcional `REWRITE_MODE=llm` que usa Claude para reescribirlos (una llamada extra por turno).
- **Conversación:** el clasificador social es determinista; frases sociales poco comunes pueden tratarse
  como consulta (y, sin evidencia, terminar en abstención).
- **Evaluación:** los resultados del informe de pruebas miden recuperación y comportamiento con preguntas
  construidas por el equipo. **No** se reporta una precisión general del sistema: no existe una evaluación
  con usuarios reales que la respalde.
- **Autenticación:** solo modo invitado (sin registro ni roles). El historial de invitados se elimina a los 7 días.
- **Presupuesto:** al alcanzar `ANTHROPIC_BUDGET_USD` el backend deja de llamar a Claude hasta que se eleve
  el límite; los saludos y la búsqueda siguen funcionando.
