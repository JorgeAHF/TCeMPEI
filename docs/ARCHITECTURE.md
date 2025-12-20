# Arquitectura propuesta y entendimiento

Este documento resume la interpretación de la **Especificación Maestra v1.1** y la arquitectura objetivo antes de continuar con la implementación completa.

## Objetivos clave
- Catálogo versionado de puentes, tirantes, torones, sensores e instalaciones con auditoría mínima.
- Ingesta de campañas CSV (crudo + normalizado) con mapeo columna→sensor→tirante y hash SHA256.
- Registro de campañas de pesaje directo, creación de snapshots y versionado de calibraciones K.
- Ejecución de análisis espectral (Welch + ventana Hann, segmentación por porcentaje, detección de picos, validación armónica) guardando runs y resultados sin sobreescritura.
- Consulta histórica y semáforo estructural (T > 0.45·Fu usando estado y Fu vigentes).

## Capas
- **Datos (PostgreSQL + SQLAlchemy)**: Esquema relacional con claves foráneas, restricciones y trazabilidad (created_at/by). No se borra historial; nuevas versiones/rangos reemplazan vigencias anteriores.
- **Servicios de negocio (Python)**: Funciones puras para selección de estado vigente, K vigente, validación de solapes de instalación, cálculo de tensión `T = k * f0^2`, generación de CSV normalizado y validaciones de reglas críticas. No dependen de Dash.
- **UI Dash**: Wizards y vistas para catálogo, adquisiciones, pesajes, análisis, histórico y semáforo. Plotly para gráficas; DataTable con scroll horizontal para resultados.
- **Infraestructura**: Docker Compose para PostgreSQL + app. Carpetas `/data/raw`, `/data/normalized`, `/data/attachments` configurables.

## Modelo de datos (vista lógica)
- **users**: credenciales locales y rol (Admin/Analista/Consulta/Invitado).
- **bridges** ↔ **cables**: un puente tiene muchos tirantes; `cables.nombre_en_puente` único por puente.
- **strand_types**: propiedades mecánicas y Fu por defecto.
- **cable_state_versions**: versiones con vigencia (`valid_from/valid_to`), L efectiva, μ, activos/total, Fu_override, antivandálico. Restricciones de positividad y consistencia.
- **sensors** y **sensor_installations**: historial de instalaciones (sin solapes) con altura.
- **acquisitions**: campañas con `Fs_Hz`, operador y referencia a archivos.
- **raw_files**: registros por acquisition (crudo/normalizado) con hash SHA256 y tamaño > 0.
- **acquisition_channels**: mapeo columna→sensor→tirante con flags de warning.
- **weighing_campaigns**, **weighing_attachments**, **weighing_measurements**: captura de pesajes directos.
- **cable_config_snapshots**: congelan L, μ, activos/total y tipo de torón usado para calcular K.
- **k_calibrations**: K por tirante, derivada de pesaje + snapshot, con vigencia y algoritmo.
- **analysis_runs** + **analysis_run_params** + **analysis_results**: sesiones por acquisition; parámetros y resultados por tirante con trazabilidad (k_used_calibration_id, df_hz, armónicos, calidad).

## Flujos previstos
1. **Catálogo**: Alta/edición con versionado (nuevas versiones, no sobrescribir). Validar solapes de instalación y única versión abierta por tirante.
2. **Adquisición CSV**: Upload con DATA_START obligatorio, cálculo SHA256, registro raw_file, mapeo columna→sensor→tirante (propuesta por instalación vigente), generación de CSV normalizado y registro normalized_file.
3. **Pesaje directo**: Captura de campaña, mediciones por tirante, creación de snapshots (permite overrides), cálculo de K, definición de vigencias sin traslape.
4. **Análisis**: Selección de acquisition, creación de AnalysisRun, parametrización por tirante (segmento %, nperseg, noverlap, sigma, threshold, min_distance_hz, n_harmonics, modo f0), cálculo Welch + detección de picos + identificación armónica, guardado de resultados usando K vigente a la fecha de la acquisition.
5. **Histórico/Semáforo**: Consultas T/f0/K vs fecha, comparación de campañas, semáforo por T > 0.45·Fu vigente.

## Próximos pasos
- Completar migraciones/DDL PostgreSQL y asegurar restricciones de no solape (instalaciones y K) mediante checks o validaciones en servicios.
- Implementar servicios de normalización de CSV y parser con DATA_START + versionado de parser.
- Incorporar lógica de análisis (Welch, detección de picos, validación armónica y modo guiado) y UI correspondiente.
- Añadir scripts de inicialización (usuario admin, carpetas de datos) y pruebas adicionales para K vigente y estado vigente.
