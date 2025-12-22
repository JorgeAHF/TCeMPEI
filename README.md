# TCeMPEI

Sistema local para gestión histórica y análisis de tirantes de puentes atirantados. Incluye modelo de datos con versionado, servicios de negocio y una UI básica en Dash.

## Estructura
- `docker-compose.yml`: Levanta PostgreSQL y la app Dash.
- `app/`: Código Python (SQLAlchemy + Dash).
- `tests/`: Pruebas unitarias con pytest.
- `data/`: Almacenamiento local para archivos crudos, normalizados y adjuntos.

## Uso rápido
1. Define `DATABASE_URL` apuntando a PostgreSQL (por ejemplo `postgresql+psycopg2://postgres:postgres@db:5432/tcempei`). Docker Compose ya lo establece para desarrollo local, pero la variable es obligatoria: la app falla si no está definida.
2. Construir y levantar con Docker Compose:
   ```bash
   docker-compose up --build
   ```
3. La UI estará en http://localhost:8050.
4. Después de aplicar migraciones o de crear la base, crea el usuario administrador por defecto usando la misma `DATABASE_URL`:
   ```bash
   docker compose exec web python -m app.cli ensure-default-admin
   ```
   Usa `DEFAULT_ADMIN_EMAIL` y `DEFAULT_ADMIN_PASSWORD` para personalizar las credenciales iniciales.

### Comandos operativos
- Aplicar migraciones (usa la `DATABASE_URL` configurada, dentro del contenedor o entorno virtual):
  ```bash
  alembic upgrade head
  ```
- Crear o asegurar el administrador por defecto:
  ```bash
  python -m app.cli ensure-default-admin --email admin@example.com --password admin123
  ```
- Iniciar sesión en la UI: abre http://localhost:8050, ingresa el correo y contraseña definidos en el paso anterior y usa el botón **Entrar**. Si las credenciales son válidas, la app mostrará el dashboard y almacenará el usuario en la sesión de cliente.

### Sin Docker
```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
export DATABASE_URL=postgresql+psycopg2://usuario:password@localhost:5432/tcempei
python -m app.main
```

## Pruebas
```bash
TEST_DATABASE_URL=postgresql+psycopg2://usuario:password@localhost:5432/tcempei_test pytest
```

## Funcionalidad
- Modelo lógico completo para catálogo, adquisiciones, pesajes, snapshots y análisis con restricciones clave.
- Servicios para seleccionar estado vigente del tirante, K vigente y validación de solapes de instalación.
- Layout Dash con navegación y textos guía para los flujos (catálogo, adquisiciones, pesajes, análisis, histórico y semáforo).
- Documento de arquitectura preliminar en `docs/ARCHITECTURE.md` con la interpretación de la especificación y el modelo de datos.
