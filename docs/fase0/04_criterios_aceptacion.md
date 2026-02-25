# Criterios de Aceptacion v1 - TCeMPEI

## 1. Criterios globales
- Todo flujo productivo funciona sobre PostgreSQL.
- No existe ruta funcional dependiente de SQLite.
- Toda accion relevante esta asociada a usuario autenticado.
- Toda accion relevante deja traza de auditoria.

## 2. Catalogo estructural
- Dado un admin o analyst, cuando crea un puente/tirante con campos obligatorios, entonces se persiste y lista correctamente.
- Dado un tirante con estado vigente, cuando se intenta crear estado con vigencia solapada, entonces el sistema rechaza con error explicito.
- Dado un estado, cuando torones_activos > torones_totales, entonces el sistema rechaza.
- Dado un estado abierto, cuando se intenta crear otro abierto, entonces el sistema rechaza.

## 3. Pesajes y K
- Dado un pesaje valido, cuando se registra K derivada, entonces queda vinculada a tirante y snapshot.
- Dado una K vigente, cuando se crea una nueva con reemplazo, entonces la vigencia anterior queda cerrada segun regla definida.
- Dado una fecha de analisis, cuando no existe K vigente unica, entonces el guardado de resultado se bloquea con error explicito.

## 4. Campanas e ingesta
- Dado un CSV valido con DATA_START, cuando se sube, entonces raw se persiste inmutable con hash y metadatos.
- Dado un CSV sin DATA_START detectable, cuando el usuario define cabecera manual, entonces el sistema permite continuar.
- Dado un mapeo invalido (duplicados no intencionales, columna inexistente, altura invalida), entonces normalizacion se bloquea y explica causa.
- Dado un mapeo valido, cuando se normaliza, entonces se genera archivo normalizado versionado y registro de canales.
- Dado un raw duplicado por hash en misma campaña, entonces el sistema bloquea.

## 5. Analisis dinamico
- Dado una señal cargada, la UI muestra acelerograma completo, segmento, FFT y PSD Welch.
- Dado parametros editados, cuando se guarda corrida, entonces persiste parametros exactos, f0 elegida, K usada, T calculada, calidad y usuario.
- Dado f0 manual, cuando el usuario confirma, entonces el sistema la usa para el calculo T = f^2 * K.

## 6. Aprobacion, resumen e historico
- Dado multiples corridas por tirante+campaña+archivo, cuando se aprueba una nueva, entonces solo una queda vigente.
- Dado una campaña, cuando se abre resumen, entonces muestra minimo: tirante, f0, T, K usada, fecha, estado, aprobado_por.
- Dado un tirante, cuando se abre historico, entonces muestra evolucion temporal de f0, T y K usada.
- Semaforo:
- OK si %Fu <= 40.
- PREALERTA si 40 < %Fu <= 45.
- ALERTA si %Fu > 45.

## 7. Seguridad y auditoria
- Dado credenciales invalidas, login responde error claro.
- Dado usuario sin permiso, accion protegida responde 403 y no altera datos.
- Dado una accion auditable, se registra usuario, fecha, accion, entidad, antes/despues, motivo (si aplica) e IP.
- La bitacora se puede exportar en CSV y JSON.

## 8. Operacion y no funcionales
- Healthchecks de contenedores disponibles.
- Tiempo de respuesta de consultas comunes < 3 s con dataset objetivo.
- Carga/normalizacion archivo tipico < 30 s.
- Ajuste interactivo de analisis < 5 s en condiciones normales.

## 9. Cobertura minima de pruebas
- Unitarias de reglas de vigencia y validaciones.
- Integracion API + PostgreSQL de flujos criticos.
- Smoke UI de login, catalogo, ingesta, analisis y aprobacion.

## 10. Casos criticos obligatorios de pasar
- Vigencia unica de K por fecha.
- No solape de estados de tirante.
- Trazabilidad por usuario en CRUD y aprobacion.
- Reproducibilidad de corrida de analisis con mismos parametros.
