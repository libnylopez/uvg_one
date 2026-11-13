# Informe de consumo de la API de Anthropic — UVG ONE

Generado a partir de `backend/data/usage/anthropic_usage.jsonl` (una línea por llamada; sin claves,
prompts ni respuestas).

## Configuración

| Parámetro | Valor |
|---|---|
| Modelo | `claude-haiku-5-5` |
| Precio (prompts ≤ 100 000 tokens) | US$0.10 por millón de tokens de entrada · US$0.50 por millón de salida |
| Fuente del precio | https://platform.claude.com/docs/en/about-claude/pricing (consultado el 13/11/2026) |
| Presupuesto de seguridad | US$0.50 (comprobado antes de cada llamada) |
| Tope de salida por llamada | 4 000 tokens |
| Reintentos automáticos | 1 (clave, saldo o permisos: sin reintento) |

## Consumo total registrado

| Concepto | Valor |
|---|---|
| Llamadas | 26 (0 fallidas) |
| Tokens de entrada | 114 853 |
| Tokens de salida (incluye razonamiento interno) | 9 068 |
| **Costo estimado total** | **US$0.0160** (3.2 % del presupuesto) |
| Llamadas `respuesta_verificada` | 26 |

El total incluye la corrida de validación y las repeticiones de consultas tras corregir problemas
(V02 tras afinar la página citada; V05, V10, V19 y V20 tras mejorar la recuperación y el prompt).

## Validación final (20 consultas)

| Concepto | Valor |
|---|---|
| Consultas con llamada a Claude | 19 de 20 |
| Costo de la corrida vigente | US$0.0121 |
| Costo medio por consulta respondida | US$0.00064 |
| Tokens medios por consulta (entrada / salida) | 4481 / 381 |

## Pruebas locales

0 llamadas: pruebas unitarias con dobles, recuperación sin LLM e integración en modo simulado
(el registro de consumo no cambió durante esas pruebas).

## Proyección

Con el costo medio medido, US$0.50 alcanzan para unas 782 consultas respondidas. Saludos y preguntas sin evidencia no consumen tokens.
