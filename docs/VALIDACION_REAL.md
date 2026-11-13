# Validación real con Claude — UVG ONE

Modelo `claude-haiku-5-5`. Revisión **determinista** (sin usar a Claude como evaluador):

- **Fundamentación:** las fuentes citadas están entre los pasajes recuperados, y cada cifra, fecha, monto
  o correo de la respuesta aparece literalmente en esa evidencia.
- **Relevancia:** se cita el documento esperado y la respuesta contiene los datos clave del criterio.
- **Abstención:** la respuesta debe ser `abstained`.

Además, cada respuesta se **leyó manualmente** y sus datos se contrastaron con el texto de los PDF
(ver «Revisión manual»).

## Resumen

- Consultas: **20** · aprobadas por las comprobaciones: **20/20**
- Llamadas a Claude: 19 · costo de esta corrida: **US$0.0121**
- Tiempo de respuesta (consultas con Claude): promedio 2.5 s, máximo 4.5 s

| Categoría | Aprobadas |
|---|---|
| Directa | 8/8 |
| Seguimiento | 3/3 |
| Relacional | 4/4 |
| Abstención | 3/3 |
| Informal / errores ortográficos | 2/2 |

## Resultados por consulta

| Id | Categoría | Pregunta | Documento esperado | Estado | Fuentes citadas | Fundamentación | Relevancia | Tiempo | Tokens (ent./sal.) | Costo US$ |
|---|---|---|---|---|---|---|---|---|---|---|
| V01 | Directa | ¿Cuánto cuesta cada nivel del programa de inglés del Centro de Idiomas? | Centro de Idiomas | answered | Centro de Idiomas 2025 · Develop your potencial in: · pág. 2 | fuentes⊂evidencia=sí; cifras verificadas 9/9 | documento esperado citado=sí; datos clave completos | 3.33 s | 3815/240 | 0.00050 |
| V02 | Directa | ¿Cuál es el último día para pagar la cuota de septiembre sin recargo? | Calendario | answered | Calendario Académico · — · págs. 3–4 | fuentes⊂evidencia=sí; cifras verificadas 1/1 | documento esperado citado=sí; datos clave completos | 1.49 s | 4186/103 | 0.00047 |
| V03 | Directa | ¿Cuáles son los pasos para inscribirme como estudiante de primer ingreso? | Proceso de Admisión | answered | Proceso de Admisión e Inscripción Estudiante de Primer Ingreso · — · pág. 1 | fuentes⊂evidencia=sí; cifras verificadas 0/0 | documento esperado citado=sí; datos clave completos | 2.62 s | 3754/489 | 0.00062 |
| V04 | Directa | ¿Qué tipos de ayuda financiera ofrece la universidad? | ayudas financieras | answered | Reglamento de ayudas financieras · Capítulo 1 · Artículo 7. Tipos de ayudas financieras · pág. 4; Reglamento de ayudas financieras · Capítulo IV · Artículo 13.… | fuentes⊂evidencia=sí; cifras verificadas 1/1 | documento esperado citado=sí; datos clave completos | 2.48 s | 5000/441 | 0.00072 |
| V05 | Directa | ¿Cuánto dura la Licenciatura en Turismo? | Turismo | answered | Turismo 2025 · Proyectos y prácticas · pág. 2; Turismo 2025 · Desarrollar estrategias de mercadeo turístico · pág. 2 | fuentes⊂evidencia=sí; cifras verificadas 1/1 | documento esperado citado=sí; datos clave completos | 1.69 s | 3720/168 | 0.00046 |
| V13 | Seguimiento | ¿En qué modalidad se imparte esa carrera? | Turismo | answered | Turismo 2025 · Desarrollar estrategias de mercadeo turístico · pág. 2 | fuentes⊂evidencia=sí; cifras verificadas 1/1 | documento esperado citado=sí; datos clave completos | 1.8 s | 4016/99 | 0.00045 |
| V14 | Seguimiento | ¿Y qué puede hacer un egresado? | Turismo | answered | Turismo 2025 · Proyectos y prácticas · pág. 2; Turismo 2025 · Desarrollar estrategias de mercadeo turístico · pág. 2 | fuentes⊂evidencia=sí; cifras verificadas 1/1 | documento esperado citado=sí; datos clave completos | 2.46 s | 3950/392 | 0.00059 |
| V15 | Seguimiento | ¿Dónde pido más información? | Turismo | answered | Turismo 2025 · Desarrollar estrategias de mercadeo turístico · pág. 2 | fuentes⊂evidencia=sí; cifras verificadas 6/6 | documento esperado citado=sí; datos clave completos | 1.48 s | 4199/200 | 0.00052 |
| V06 | Directa | ¿Qué requisitos debe cumplir un estudiante para integrar la junta directiva de una asociación estudiantil? | grupos estudiantiles | answered | Reglamento de grupos estudiantiles · Capítulo 2 · Artículo 12 · págs. 6–7; Reglamento de grupos estudiantiles · Capítulo 2 · Artículo 12 · pág. 7; Reglamento d… | fuentes⊂evidencia=sí; cifras verificadas 1/1 | documento esperado citado=sí; datos clave completos | 3.04 s | 4611/440 | 0.00068 |
| V07 | Directa | ¿Qué es el Instituto Tecnológico ITEC? | ITEC | answered | ITEC 2025 · Para más información de · pág. 2 | fuentes⊂evidencia=sí; cifras verificadas 1/1 | documento esperado citado=sí; datos clave completos | 3.1 s | 3642/503 | 0.00062 |
| V08 | Directa | ¿Cuándo es la semana de inscripción y asignación de cursos para el primer ciclo 2027? | Calendario | answered | Calendario Académico · — · págs. 5–6; Calendario Académico · — · págs. 6–7 | fuentes⊂evidencia=sí; cifras verificadas 2/2 | documento esperado citado=sí; datos clave completos | 1.75 s | 4171/265 | 0.00055 |
| V09 | Relacional | ¿Qué carreras ofrece la UVG Altiplano? | Bifoliar\|Informática\|Turismo\|Agroforestería | answered | Maestría 2025 · — · págs. 1–2; Informática 2025 · — · págs. 1–2; Educación Física 2025 · — · pág. 1; Agroforestería 2025 · — · pág. 1; Tecnología Industrial 20… | fuentes⊂evidencia=sí; cifras verificadas 0/0 | documento esperado citado=sí; datos clave completos | 3.2 s | 4515/712 | 0.00081 |
| V10 | Relacional | ¿Qué ingenierías ofrece la UVG Altiplano y cuánto duran? | Agroforestería\|Tecnología Industrial\|Agrícola | answered | Agroforestería 2025 · Manejar cultivos bajo condiciones controladas · pág. 2; Tecnología Industrial 2025 1 · Diseñar, acelerar y diversificar procesos industri… | fuentes⊂evidencia=sí; cifras verificadas 1/1 | documento esperado citado=sí; datos clave completos | 3.55 s | 4942/585 | 0.00079 |
| V11 | Relacional | ¿Qué fechas de pruebas de admisión aparecen en el calendario académico? | Calendario | answered | Calendario Académico · — · págs. 3–4; Calendario Académico · — · págs. 6–7 | fuentes⊂evidencia=sí; cifras verificadas 7/7 | documento esperado citado=sí; datos clave completos | 4.54 s | 4198/955 | 0.00090 |
| V12 | Relacional | ¿Qué condiciones establece el artículo 18 del reglamento de ayudas financieras y de qué depende la renovación de una ayuda? | ayudas financieras | answered | Reglamento de ayudas financieras · Capítulo III · Artículo 11. Dirección de Ayudas Financieras · pág. 6; Reglamento de ayudas financieras · Capítulo IV · Artíc… | fuentes⊂evidencia=sí; cifras verificadas 2/2 | documento esperado citado=sí; datos clave completos | 2.81 s | 7253/594 | 0.00102 |
| V16 | Abstención | ¿Cuánto cuesta la carrera de Medicina en la UVG Altiplano? | — | abstained | — | abstención correcta | n/a | 1.67 s | 4405/276 | 0.00058 |
| V17 | Abstención | ¿Quién es el rector de la Universidad del Valle de Guatemala? | — | abstained | — | abstención correcta | n/a | 2.22 s | 5291/177 | 0.00062 |
| V18 | Abstención | ¿Cuál es la capital de Francia? | — | abstained | — | abstención correcta | n/a | 0.07 s | 0/0 | 0.00000 |
| V19 | Informal / errores ortográficos | cuanto cuesta el curzo de ingles | Centro de Idiomas | answered | Centro de Idiomas 2025 · Develop your potencial in: · pág. 2 | fuentes⊂evidencia=sí; cifras verificadas 4/4 | documento esperado citado=sí; datos clave completos | 1.39 s | 5036/189 | 0.00060 |
| V20 | Informal / errores ortográficos | q necesito pa inscribirme en la u | Proceso de Admisión | answered | Proceso de Admisión e Inscripción Estudiante de Primer Ingreso · — · pág. 1 | fuentes⊂evidencia=sí; cifras verificadas 0/0 | documento esperado citado=sí; datos clave completos | 2.29 s | 4435/411 | 0.00065 |

## Revisión manual

Se leyó cada respuesta y se buscaron en el texto de los PDF todos los datos que no son evidentes
(fechas del calendario de noviembre a enero, duraciones, promedios, extensiones y correos).
**No se encontró ningún dato inventado.**

Problemas detectados en la primera corrida y corregidos (las consultas afectadas se repitieron):

| Consulta | Problema | Corrección |
|---|---|---|
| V02 | Citaba la pág. 2 del calendario (agosto) para un dato de la pág. 3 | En pasajes fusionados se cita la página del fragmento que contiene la respuesta |
| V10 | «La duración no aparece» y la maestría colada en el contexto | La parte «y cuánto duran» se busca dentro de los folletos encontrados, con sinónimos («años», «total de la carrera») |
| V05 | Dudaba de la duración total de la carrera | Regla en el prompt sobre cómo los folletos indican la duración por etapas |
| V20 | Respondía los requisitos para ser «lead» en lugar de la inscripción | Sinónimos de «qué necesito para inscribirme» (solicitud, documentos, DPI) |
| V19 | La respuesta contenía la palabra «Inglell» (error del propio modelo) | No se reprodujo al repetir la consulta |

Observaciones que se mantienen:

- **V10** dice «hay dos ingenierías» y luego menciona una tercera (Agroforestal); los datos de las tres son correctos.
- **V20** describe bien los pasos, pero indica que no aparece la lista de documentos, aunque el proceso
  menciona foto, DPI y certificación de cursos aprobados.
- **V16 y V17** se abstuvieron correctamente, pero usaron una llamada: la búsqueda halló pasajes
  relacionados y fue la verificación de Claude la que determinó que no respaldaban una respuesta.
- Las secciones de los folletos muestran títulos de bloque del PDF poco descriptivos.

## Respuestas completas

### V01 — ¿Cuánto cuesta cada nivel del programa de inglés del Centro de Idiomas?

*Criterio:* Q500.00 por nivel (bimestral); puede mencionar libro Q200 y evaluación Q30.  
*Documentos recuperados:* Centro de Idiomas 2025

> Según el Centro de Idiomas 2025, el costo por nivel del Programa de Cursos Libres de Inglés es de **Q500.00**, con cobro bimestral (son cinco niveles al año). Además, hay otros pagos mencionados en el mismo folleto: Q200.00 por la compra del libro y Q30.00 por la evaluación de ubicación. Para más información puedes comunicarte al PBX 7931-0814, extensiones 41306 o 41307, o escribir a ca.cei@uvg.edu.gt.

### V02 — ¿Cuál es el último día para pagar la cuota de septiembre sin recargo?

*Criterio:* 17 de septiembre.  
*Documentos recuperados:* Calendario Académico

> El último día para pagar la cuota de estudios de septiembre sin recargo es el **17 de septiembre**, según el Calendario académico.

### V03 — ¿Cuáles son los pasos para inscribirme como estudiante de primer ingreso?

*Criterio:* Solicitud y validación de datos, inscripción, pago de matrícula y asignación de cursos.  
*Documentos recuperados:* Proceso de Admisión e Inscripción Estudiante de Primer Ingreso

> Para inscribirte como estudiante de primer ingreso en la UVG Campus Altiplano, según el documento de Proceso de Admisión e Inscripción, el camino es el siguiente:
>
> 1. **Revisión y validación de datos:** Admisiones verifica que la solicitud esté completa, incluyendo nombre, fecha de nacimiento, CUI, dirección, teléfonos, correo, información del grado anterior, carrera de interés y sede, y que se suban la foto, el DPI y la certificación de cursos aprobados.
> 2. **Solicitud de ayuda financiera (si aplica):** Se te brinda la información de requisitos y acompañamiento para llenar el formulario.
> 3. **Inscripción:** Se registran tus datos y los de ambos padres, y firmas la carta de compromiso de pago y de responsabilidad y eximente. Luego se crea tu carné y el expediente se archiva en carpeta digital.
> 4. **Pago de matrícula:** Cuentas por Cobrar te informa sobre fechas y medios de pago.
> 5. **Asignación de cursos:** Una vez confirmado el pago, el Director de carrera te asigna los cursos.
>
> El documento no detalla fechas específicas ni montos de pago.

### V04 — ¿Qué tipos de ayuda financiera ofrece la universidad?

*Criterio:* Beca, crédito educativo y subsidio por auxiliatura (Art. 7).  
*Documentos recuperados:* Reglamento de ayudas financieras

> En la UVG puedes acceder a distintos tipos de apoyo económico. Según el Reglamento de ayudas financieras, los tipos de ayuda son:
>
> - **Beca:** ayuda no reembolsable que se otorga en porcentajes definidos según la situación socioeconómica del estudiante y/o las condiciones de los programas vigentes.
> - **Crédito educativo:** ayuda económica que el estudiante debe reembolsar a la Universidad, otorgada según su situación socioeconómica y su capacidad de pago.
> - **Subsidio por auxiliatura:** monto que se acredita a la cuenta corriente del estudiante cuando es nombrado auxiliar en determinados cursos o actividades institucionales, regido por el UVG.DGE.02.002 Reglamento de Auxiliares.
>
> Estas ayudas pueden aplicarse individualmente o combinadas, según las condiciones de cada programa. Dentro del Programa Regular, la beca y el crédito educativo pueden combinarse, y el porcentaje depende de la evaluación socioeconómica del estudiante.

### V05 — ¿Cuánto dura la Licenciatura en Turismo?

*Criterio:* 5 años en total (técnico 2 años + licenciatura 3 años).  
*Documentos recuperados:* Turismo 2025

> La **Licenciatura en Turismo** de la UVG Altiplano tiene una duración de **3 años** como etapa de licenciatura, según el folleto de Turismo 2025. Si cuentas también el Técnico Universitario en Turismo, de 2 años, el **total de la carrera** es de **5 años**.

### V13 — ¿En qué modalidad se imparte esa carrera?

*Criterio:* Modalidad B-Learning (referente: Turismo).  
*Documentos recuperados:* Turismo 2025

> La Licenciatura en Turismo se imparte en modalidad **B-Learning**, según el folleto Turismo 2025.

### V14 — ¿Y qué puede hacer un egresado?

*Criterio:* Perfil del egresado de Turismo (proyectos turísticos sostenibles).  
*Documentos recuperados:* Turismo 2025

> Según el folleto Turismo 2025, el egresado de la Licenciatura en Turismo puede desempeñarse en entornos turísticos y de servicios, aplicando conocimientos en gestión hotelera, planificación de destinos, marketing turístico y sostenibilidad. También puede supervisar, coordinar y liderar equipos enfocados en organización de eventos, diseño de experiencias turísticas y mejora de la calidad en servicios, así como diseñar itinerarios y paquetes turísticos. El documento indica que estas experiencias pueden darse en hoteles, restaurantes, agencias de viajes, empresas de transporte turístico, parques naturales, reservas privadas, entidades gubernamentales y proyectos de ONG, y menciona como perfil liderar proyectos turísticos sostenibles con enfoque cultural, ambiental y económico. Lo que no aparece en el material es un listado de cargos específicos ni datos sobre empleabilidad o salarios.

### V15 — ¿Dónde pido más información?

*Criterio:* Correo ca.turismo@uvg.edu.gt / PBX del folleto de Turismo.  
*Documentos recuperados:* Turismo 2025

> Para información sobre la Licenciatura en Turismo, el folleto Turismo 2025 indica el teléfono PBX 7931-0814, extensiones 41205 y 41203, y el correo ca.turismo@uvg.edu.gt. Esos son los datos de contacto que aparecen en el material, así que puedes escribir o llamar a esas líneas para consultar la duración total de la carrera o cualquier otra duda.

### V06 — ¿Qué requisitos debe cumplir un estudiante para integrar la junta directiva de una asociación estudiantil?

*Criterio:* Promedio mínimo de 70, no haber reprobado cursos, sin condicionamientos, etc.  
*Documentos recuperados:* Reglamento de grupos estudiantiles

> Para postularte a la junta directiva de la AEUVG, AESur o AEAltiplano, el Reglamento de grupos estudiantiles establece tres requisitos básicos que deben cumplirse por todos los postulados: estar inscrito, asignado y cursando la carrera según el cargo al que aspiras, tener un promedio mínimo de 70 puntos y no haber reprobado ningún curso.
>
> En cuanto al año de la carrera, el reglamento lo distingue según el cargo:
>
> - **Presidente:** entre segundo y penúltimo año de la carrera.
> - **Vicepresidente:** entre segundo y penúltimo año de la carrera.
> - **Secretario:** cualquier año de la carrera.
>
> Además, si ya tomaste posesión y luego dejas de cumplir alguno de estos requisitos, no puedes seguir ejerciendo el cargo. Para la presentación formal de la planilla, el reglamento pide la planilla completa, la descripción general de la asociación y la aceptación firmada del Reglamento de Grupos Estudiantiles.

### V07 — ¿Qué es el Instituto Tecnológico ITEC?

*Criterio:* Instituto Tecnológico con niveles Básico y Bachillerato.  
*Documentos recuperados:* ITEC 2025

> El Instituto Tecnológico UVG (ITEC) es la opción de educación media de la Universidad del Valle de Guatemala, Campus Altiplano. Según el folleto ITEC 2025, ofrece formación integral de alta calidad tanto en el ciclo básico como en el ciclo diversificado, a través del Bachillerato en Ciencias y Letras. Su propuesta busca impulsar el desarrollo intelectual, el pensamiento crítico, la innovación y el emprendimiento, con participación activa en iniciativas productivas que beneficien a la comunidad, dentro de un marco de responsabilidad, ética, compromiso, respeto y excelencia.
>
> Entre sus objetivos figuran desarrollar liderazgo con base en los valores éticos del Grupo Educativo del Valle, analizar y plantear soluciones a problemáticas sociales, diseñar proyectos con impacto positivo en la comunidad y potenciar habilidades científicas, tecnológicas e innovadoras.
>
> Como egresado, según el mismo folleto, desarrollarías competencias técnicas y científicas que te preparan para continuar estudios universitarios, y recibirías formación en un idioma nacional y uno extranjero junto al Centro de Idiomas de UVG Campus Altiplano.

### V08 — ¿Cuándo es la semana de inscripción y asignación de cursos para el primer ciclo 2027?

*Criterio:* 1-6 de diciembre.  
*Documentos recuperados:* Calendario Académico

> La semana de inscripción y asignación de cursos para el primer ciclo 2027 es del **1 al 6 de diciembre**, según el Calendario Académico, en el actual Sistema de Registro Académico/Portal de estudiantes.
>
> El calendario no indica en estos fragmentos más detalles sobre esa semana, pero sí muestra que las asignaciones ordinarias en el nuevo Sistema de Registro Académico/Portal de estudiantes inician el **4 de enero de 2027**, y que las clases del primer ciclo 2027 comienzan el **18 de enero de 2027**.

### V09 — ¿Qué carreras ofrece la UVG Altiplano?

*Criterio:* Lista de programas de varios folletos (al menos 5 fuentes distintas).  
*Documentos recuperados:* Maestría 2025, Bifoliar General 2025, Informática 2025, Educación Física 2025, Agroforestería 2025, Tecnología Industrial 2025 1, Centro de Idiomas 2025, Facultad de Educación 2025, Administración de Empresas 2025, ITEC 2025, Turismo 2025, Industrialización de Alimentos 2025

> En la UVG Campus Altiplano puedes estudiar una variedad de programas en distintas áreas. Según los folletos oficiales, se mencionan los siguientes:
>
> - **Maestría**: programa de posgrado de 2 años, que incluye cierre de pensum y trabajo de graduación, de la Facultad de Ciencias Sociales.
> - **Licenciatura en Tecnología de Sistemas Informáticos**: el folleto de Informática la presenta como carrera de la oferta del campus.
> - **Profesorado y Licenciatura en Educación Física, Deporte y Recreación Física**: el folleto de Educación Física indica que tiene una duración de 2 años.
> - **Ingeniería en Tecnología Agroforestal**: aparece en el folleto de Agroforestería.
> - **Ingeniería Industrial**: aparece en el folleto de Tecnología Industrial.
> - **Profesorados y Licenciaturas en Educación**: mencionados en el folleto de la Facultad de Educación.
> - **Licenciatura en Administración de Empresas y Mercadeo**: aparece en el folleto de Administración de Empresas.
> - **Licenciatura en Turismo**: aparece en el folleto de Turismo.
> - **Licenciatura en Tecnología para la Industrialización de Alimentos**: aparece en el folleto de Industrialización de Alimentos.
> - **Instituto Tecnológico (ITEC)**: ofrece formación en el Nivel de Educación Media, en ciclo básico y en Bachillerato en Ciencias y Letras.
>
> Además, el Centro de Idiomas del campus aparece en los documentos como parte de la oferta de formación en idiomas. Los fragmentos no detallan los planes de estudio de cada programa ni sus requisitos de admisión.

### V10 — ¿Qué ingenierías ofrece la UVG Altiplano y cuánto duran?

*Criterio:* Ingenierías Agroforestal, Industrial y Agrícola y Pecuaria; duración de 5 años (2 técnico + 3).  
*Documentos recuperados:* Agroforestería 2025, Tecnología Industrial 2025 1, Maestría 2025, ITEC 2025, Agrícola y Pecuaria 2025, Informática 2025, Facultad de Educación 2025, Educación Física 2025, Administración de Empresas 2025

> En la UVG Campus Altiplano hay dos ingenierías que aparecen en los folletos: **Ingeniería en Tecnología Agrícola y Pecuaria** y **Ingeniería en Tecnología Industrial**.
>
> - **Ingeniería en Tecnología Agrícola y Pecuaria:** según el folleto de Agrícola y Pecuaria 2025, la carrera tiene Técnico Universitario en Productos Agrícolas de Exportación de 2 años, Ingeniería en Tecnología Agrícola y Pecuaria de 3 años y un total de 5 años.
> - **Ingeniería en Tecnología Industrial:** el folleto de Tecnología Industrial 2025 indica Técnico Universitario en Mecatrónica de 2 años, Ingeniería en Tecnología Industrial de 3 años y un total de 5 años.
>
> Además, el folleto de Agroforestería 2025 menciona una Ingeniería en Tecnología Agroforestal de 3 años con un total de 5 años, aunque en el mismo material aparece la etiqueta de Técnico de 2 años.
>
> Los fragmentos no indican cuánto dura cada ingeniería por separado en el caso de Agroforestería más allá de lo anterior, ni si hay otras ingenierías fuera de estas tres.

### V11 — ¿Qué fechas de pruebas de admisión aparecen en el calendario académico?

*Criterio:* Varias fechas de pruebas de admisión (agosto, septiembre, octubre, diciembre).  
*Documentos recuperados:* Calendario Académico

> En el Calendario académico aparecen varias pruebas de admisión. Algunas ya pasaron y estas son las que quedan a partir de hoy:
>
> - **18 de noviembre de 2026**: prueba de admisión presencial.
> - **5 de diciembre de 2026**: prueba de admisión presencial.
> - **8 de diciembre de 2026**: prueba de admisión presencial.
> - **12 de diciembre de 2026**: prueba de admisión presencial.
> - **6 de enero de 2027**: prueba de admisión presencial.
> - **9 de enero de 2027**: prueba de admisión presencial.
>
> El calendario también registra pruebas de septiembre, octubre y noviembre de 2026 (29 de septiembre, 3 de octubre, 16 y 17 de octubre, y 7 de noviembre en modalidad híbrida), que ya tuvieron lugar. El calendario que tengo termina antes de cubrir fechas posteriores a enero de 2027.

### V12 — ¿Qué condiciones establece el artículo 18 del reglamento de ayudas financieras y de qué depende la renovación de una ayuda?

*Criterio:* Condiciones del Art. 18 (carga completa, etc.) y renovación según rendimiento académico (Art. 6).  
*Documentos recuperados:* Reglamento de ayudas financieras

> El **Artículo 18** del Reglamento de ayudas financieras, dentro del Capítulo IV sobre el campus central, fija las condiciones que deben cumplir los beneficiarios, pero la tabla que las distribuye por programa no conserva sus marcas, así que no puedo indicar con certeza qué condición aplica a cada programa. Las condiciones que sí aparecen son las siguientes:
>
> - **Carga y promedio:** mantener la carga completa en cada semestre, según el plan de estudios, con un promedio mínimo de 65 puntos.
> - **Firma del reconocimiento:** firmar el "Reconocimiento unilateral por otorgamiento de beca" en las fechas que indique la UVG; en el caso del crédito educativo, el estudiante y su fiador deben firmar el "Reconocimiento de deuda por subvención de crédito educativo" en las fechas especificadas.
> - **Horas de beca:** cumplir con las horas beca asignadas por el Departamento de Ayudas Financieras.
> - **Normas institucionales:** cumplir con el "Código de Comportamiento de los Estudiantes", el "Código de Ética del Grupo Educativo del Valle" y el propio Reglamento de Ayudas Financieras.
>
> Sobre la renovación, el reglamento indica que está sujeta al rendimiento académico de los estudiantes y al cumplimiento de los criterios de cada subprograma. Los documentos que tengo no detallan cómo se calcula ese rendimiento académico.

### V16 — ¿Cuánto cuesta la carrera de Medicina en la UVG Altiplano?

*Criterio:* No hay Medicina en los documentos: debe abstenerse sin inventar un costo.  
*Documentos recuperados:* Maestría 2025, Informática 2025, Reglamento de ayudas financieras, Facultad de Educación 2025, Proceso de Admisión e Inscripción Estudiante de Primer Ingreso, Administración de Empresas 2025

> Encontré documentos relacionados con tu pregunta, pero no dicen lo suficiente como para responderte con seguridad, y prefiero no darte un dato que no pueda respaldar.
>
> Lo más cercano que encontré está en **Maestría 2025**, por si quieres revisarlo.

### V17 — ¿Quién es el rector de la Universidad del Valle de Guatemala?

*Criterio:* No aparece en los documentos: debe abstenerse.  
*Documentos recuperados:* Reglamento de grupos estudiantiles

> Encontré documentos relacionados con tu pregunta, pero no dicen lo suficiente como para responderte con seguridad, y prefiero no darte un dato que no pueda respaldar.
>
> Lo más cercano que encontré está en **Reglamento de grupos estudiantiles** (Capítulo 2 · Artículo 4. Sistema electoral), por si quieres revisarlo.

### V18 — ¿Cuál es la capital de Francia?

*Criterio:* Fuera de dominio: abstención local, sin llamar a Claude.  
*Documentos recuperados:* —

> No encontré información sobre eso en los documentos oficiales que tengo disponibles.
>
> Puede que el tema no esté cubierto, o que con otras palabras sí lo encuentre. Intenta ser más específico, por ejemplo: «requisitos de admisión para primer ingreso» o «fechas del calendario académico».

### V19 — cuanto cuesta el curzo de ingles

*Criterio:* Errores ortográficos: igual que V01 (Q500.00 por nivel).  
*Documentos recuperados:* Centro de Idiomas 2025, Reglamento de ayudas financieras

> En el Centro de Idiomas de la UVG Altiplano el curso libre de inglés se cobra por niveles. Según el folleto Centro de Idiomas 2025, el costo por nivel es de Q500.00, con cobro bimestral y 5 niveles al año. Además, se debe considerar la compra del libro por Q200.00 y la evaluación de ubicación por Q30.00.

### V20 — q necesito pa inscribirme en la u

*Criterio:* Lenguaje informal: pasos/requisitos de inscripción de primer ingreso.  
*Documentos recuperados:* Proceso de Admisión e Inscripción Estudiante de Primer Ingreso, Reglamento de grupos estudiantiles, Reglamento de ayudas financieras, ITEC 2025

> Para inscribirte como estudiante de primer ingreso en UVG Campus Altiplano, el proceso que describen los documentos pasa por varias etapas. Según el documento *Proceso de Admisión e Inscripción Estudiante de Primer Ingreso*, después del contacto inicial y la revisión de datos de tu solicitud de admisión, el Director de carrera asigna tus cursos. La inscripción incluye registrar tu información y la de ambos padres, confirmar que todo esté completo y correcto para crear tu carné, y firmar la carta de compromiso de pago y de responsabilidad y eximente. Tu expediente se recibe y se archiva en carpeta digital. Si necesitas apoyo económico, también se te brinda información sobre los requisitos de ayuda financiera y acompañamiento para llenar el formulario, y el proceso incluye un pago.
>
> No aparece en los documentos que tengo la lista completa de documentos que debes presentar para la admisión ni las fechas de inscripción.

