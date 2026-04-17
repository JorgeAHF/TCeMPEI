# TCeMPEI

Sistema local para gestión histórica y análisis de tirantes de puentes atirantados (CeMPEI/IMT).

## Qué incluye ahora
- Esquema PostgreSQL alineado con la especificación (versionado de tirantes, mapeo de adquisiciones, pesajes, K, análisis y semáforo).
- Lógica de negocio mínima (Python) para selección de estado vigente, K vigente, cálculo de Fu efectivo y validación de solapamientos de instalaciones.
- Pruebas unitarias básicas (pytest) para las reglas críticas anteriores.
- Docker Compose con Postgres, backend FastAPI y frontend React + Vite + react-plotly.js.
- Script de inicialización de carpetas y carga de esquema.

## Estructura
- `docker-compose.yml`: orquesta Postgres (puerto 5432), backend (puerto 8000) y frontend (puerto 5173).
- `backend/requirements.txt`: dependencias del backend FastAPI/SQLAlchemy/pytest.
- `backend/Dockerfile`: imagen del backend.
- `backend/app/main.py`: FastAPI (health/info, auto creación de carpetas).
- `frontend/src`: aplicación React con rutas para catálogo, adquisiciones, pesajes, análisis, histórico y semáforo.
- `frontend/Dockerfile`: build estático del frontend servido con Nginx.
- Ingesta inicial de adquisiciones: subir CSV crudo, registrar hash y normalizar con mapeo columna→sensor→cable (flags de instalación).
- Preview de análisis dinámico: endpoint para acelerograma completo/segmento, FFT, PSD Welch y sugerencia asistida de f0.
- Semáforo/histórico: semáforo con ranking opcional top N, histórico con gráficas T y f0 por tirante.
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
# Frontend: http://localhost:5173

# 4) Migraciones (alembic)
docker-compose run --rm backend bash -lc "cd /app && alembic -c alembic.ini upgrade head"

# 5) Pruebas
docker-compose run --rm backend bash -lc "cd /app && PYTHONPATH=/app pytest"

# 6) (opcional) Frontend local con Vite
# cd frontend
# npm install
# npm run dev -- --host 0.0.0.0 --port 5173
```

## Autenticación
- Login (access+refresh): `POST /auth/login` con form `username`/`password`.
- Compatibilidad OAuth2: `POST /auth/token` (mantiene formato bearer).
- Renovar access token: `POST /auth/refresh`.
- Cerrar sesión (revoca refresh): `POST /auth/logout`.
- Preview análisis interactivo: `POST /analysis-runs/{run_id}/preview`.
- Requiere bearer token en endpoints protegidos. Roles base: admin, analyst, reviewer, viewer.

### Uso básico desde la UI React
1. Consigue un token JWT: `curl -X POST -F "username=TU_USER" -F "password=TU_PASS" http://localhost:8000/auth/token` (el JSON trae `access_token`).
2. Abre la UI en `http://localhost:5173/login`.
3. Inicia sesión con usuario/contraseña; el frontend maneja `access_token` en memoria y `refresh_token` en `localStorage`.
4. El frontend usa proxy `/api` hacia el backend, así que no hace falta configurar `BACKEND_URL` para el flujo normal.

## Notas de catálogo
- Al crear un puente se puede indicar `num_tirantes`; el sistema genera tirantes placeholder `T-01..T-n` listos para editar su estado y propiedades.

## Documentación Fase 0
- Se agregó la documentación de cierre y planeación en `docs/fase0/README.md`.
- Incluye especificación funcional, reglas de negocio, RBAC, criterios de aceptación y backlog de Fase 1.

## Siguientes pasos sugeridos
- Implementar endpoints CRUD/seguridad (hashing, roles) y wiring real a PostgreSQL con SQLAlchemy.
- Refinar flujos UI React y cerrar validaciones/UX faltantes en adquisición, pesaje y análisis.
- Agregar scripts de ingesta de archivos (hash, storage) y selección automática de K vigente desde la DB.

