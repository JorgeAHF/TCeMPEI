# Especificacion Funcional v1 - Plataforma TCeMPEI

## 1. Objetivo
- Operar 100% el flujo tecnico catalogo->campana->analisis->aprobacion->historico en PostgreSQL, con trazabilidad completa por usuario.

## 2. Alcance v1
- Gestion de puentes, tirantes y versionado tecnico de su estado.
- Gestion de campañas de adquisicion dinamica y archivos CSV (raw inmutable + normalizado).
- Gestion de pesajes directos y ciclo de vida de constantes K versionadas.
- Analisis dinamico interactivo por tirante (acelerograma, FFT, PSD Welch; STFT fuera de v1).
- Versionado de corridas de analisis y aprobacion de resultado vigente.
- Resumen por campaña e historico por tirante.
- Sistema de autenticacion, autorizacion por roles y auditoria.
- Operacion completa en Docker con PostgreSQL como unica fuente de verdad.

## 3. Fuera de alcance v1
- Exportador avanzado PDF/Excel.
- Modulo de deteccion automatica de anomalias.
- Integracion SSO productiva.
- Integraciones SCADA/IoT y adquisicion en tiempo real.
- App movil.

## 4. Alcance v1.1
- Exportador avanzado PDF/Excel.
- Modulo de anomalias.
- Integracion SSO.

## 5. Usuarios objetivo
- Uso interno CeMPEI/IMT en v1.

## 6. Idioma y zonas horarias
- Idioma oficial UI/reportes: espanol.
- Zona horaria de base de datos: UTC.
- Zona horaria de visualizacion: America/Mexico_City.

## 7. Arquitectura y restricciones tecnicas
- Backend API: FastAPI.
- Frontend tecnico: Dash.
- Base de datos: PostgreSQL (sin SQLite para flujos de app).
- Infraestructura: Docker Compose en dev/qa/prod.
- Toda la informacion de negocio debe persistir en PostgreSQL.

## 8. Entidades principales de negocio
- Puente.
- Tirante.
- Version de estado de tirante.
- Tipo de toron.
- Sensor e instalacion.
- Campana de adquisicion.
- Archivo raw y archivo normalizado.
- Canal mapeado de adquisicion.
- Campana de pesaje y medicion.
- Snapshot de configuracion de tirante.
- Calibracion K.
- Run de analisis y resultado de analisis.
- Evento de auditoria.

## 9. Criterios globales de exito de v1
- Flujo completo operativo para al menos un puente real con trazabilidad completa.
- Cumplimiento de reglas de vigencia de estado/K sin traslapes.
- Resultado aprobado por tirante/campana/archivo visible en resumen.
- Historico de f0, T y K navegable por tirante.
- Todas las acciones relevantes auditadas y consultables.

## 10. Definicion de cierre
- Done Fase 0: requisitos cerrados y aprobados, modelo y reglas firmadas, criterios de aceptacion definidos.
- Fecha objetivo cierre Fase 0: 2026-03-11.
- Fecha objetivo inicio Fase 1: 2026-03-12.
