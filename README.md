# TCeMPEI

Sistema local para gestión histórica y análisis de tirantes de puentes atirantados (CeMPEI/IMT).

## Qué incluye ahora
- Esquema PostgreSQL alineado con la especificación (versionado de tirantes, mapeo de adquisiciones, pesajes, K, análisis y semáforo).
- Lógica de negocio mínima (Python) para selección de estado vigente, K vigente, cálculo de Fu efectivo y validación de solapamientos de instalaciones.
- Pruebas unitarias básicas (pytest) para las reglas críticas anteriores.
- Docker Compose con Postgres y backend FastAPI; Dash con sidebar prearmada.
- Script de inicialización de carpetas y carga de esquema.

## Estructura
- `docker-compose.yml`: orquesta Postgres (puerto 5432) y backend (puerto 8000).
- `backend/requirements.txt`: dependencias (FastAPI, Dash, SQLAlchemy, pytest, etc.).
- `backend/Dockerfile`: imagen del backend.
- `backend/app/main.py`: FastAPI (health/info, auto creación de carpetas).
- `backend/app/dash_app.py`: UI Dash con wizards mínimos (adquisición, pesaje, análisis) llamando a la API.
- Ingesta inicial de adquisiciones: subir CSV crudo, registrar hash y normalizar con mapeo columna→sensor→cable (flags de instalación).
- Preview de análisis dinámico: endpoint para acelerograma completo/segmento, FFT, PSD Welch y sugerencia asistida de f0.
- Semáforo/histórico: semáforo con ranking opcional top N, histórico con gráficas T y f0 por tirante.
- `backend/app/db/schema.sql`: definición completa del modelo relacional.
- `backend/app/services/business.py`: reglas vigencia K, versiones de estado, validación de instalaciones, Fu efectivo.
- `backend/app/tests/test_business.py`: pruebas Pytest de las reglas anteriores.
- `backend/app/tests/test_api.py`: prueba de flujo API (crea usuario, puente, cable, estado, K, run, semáforo alerta).
- `scripts/init_local.sh`: crea `/data` y aplica el esquema si `DATABASE_URL` está definido.

## Puesta en marcha rápida (dev)
```bash
# 1) Variables (opcional)
export DATABASE_URL=postgresql+psycopg2://cempei:cempei@localhost:5432/cempei
export DATA_ROOT=$(pwd)/data

# 2) Crear carpetas y aplicar esquema (si ya tienes Postgres arriba)
bash scripts/init_local.sh

# 3) Arrancar todo con Docker
docker-compose up --build
# API: http://localhost:8000/health
# Dash: http://localhost:8050 (se levanta con el servicio `dash` en docker-compose)

# 4) Migraciones (alembic)
docker-compose run --rm backend bash -lc "cd /app && alembic -c alembic.ini upgrade head"

# 5) Pruebas
docker-compose run --rm backend bash -lc "cd /app && PYTHONPATH=/app pytest"

# 6) (opcional) Levantar UI Dash fuera de compose
# BACKEND_URL=http://localhost:8000 python -m app.dash_app --host 0.0.0.0 --port 8050
```

## Autenticación
- Login (access+refresh): `POST /auth/login` con form `username`/`password`.
- Compatibilidad OAuth2: `POST /auth/token` (mantiene formato bearer).
- Renovar access token: `POST /auth/refresh`.
- Cerrar sesión (revoca refresh): `POST /auth/logout`.
- Preview análisis interactivo: `POST /analysis-runs/{run_id}/preview`.
- Requiere bearer token en endpoints protegidos. Roles base: admin, analyst, reviewer, viewer.

### Uso “for dummies” del token en la UI Dash
1. Consigue un token JWT: `curl -X POST -F "username=TU_USER" -F "password=TU_PASS" http://localhost:8000/auth/token` (el JSON trae `access_token`).
2. Opción A (simple): abre la UI (http://localhost:8050), ve a la pestaña “Home” y pega el `access_token` en el campo de token. Verás “Token cargado” y podrás crear/editar desde la UI.
3. Opción B: exporta la variable antes de arrancar Dash: `export DASH_TOKEN="eyJhbGciOi..."` y luego `docker-compose up` (o levanta el servicio dash). Así el token se envía automáticamente.
4. Si usas docker-compose ya corriendo y quieres lanzar Dash manualmente dentro del contenedor, asegúrate de setear `DASH_TOKEN` antes de ejecutar `python -m app.dash_app`.

## Notas de catálogo
- Al crear un puente se puede indicar `num_tirantes`; el sistema genera tirantes placeholder `T-01..T-n` listos para editar su estado y propiedades.

## Documentación Fase 0
- Se agregó la documentación de cierre y planeación en `docs/fase0/README.md`.
- Incluye especificación funcional, reglas de negocio, RBAC, criterios de aceptación y backlog de Fase 1.

## Siguientes pasos sugeridos
- Implementar endpoints CRUD/seguridad (hashing, roles) y wiring real a PostgreSQL con SQLAlchemy.
- Completar flujos UI Dash descritos en la especificación (wizards de adquisición, pesaje y análisis).
- Agregar scripts de ingesta de archivos (hash, storage) y selección automática de K vigente desde la DB.

