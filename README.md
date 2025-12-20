# TCeMPEI

Sistema local para gestión histórica y análisis de tirantes de puentes atirantados. Incluye modelo de datos con versionado, servicios de negocio y una UI básica en Dash.

## Estructura
- `docker-compose.yml`: Levanta PostgreSQL y la app Dash.
- `app/`: Código Python (SQLAlchemy + Dash).
- `tests/`: Pruebas unitarias con pytest.
- `data/`: Almacenamiento local para archivos crudos, normalizados y adjuntos.

## Uso rápido
1. Crear entorno `.env` opcional con `DATABASE_URL` y `DATA_DIR`.
2. Construir y levantar con Docker Compose:
   ```bash
   docker-compose up --build
   ```
3. La UI estará en http://localhost:8050.

### Sin Docker
```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python app/main.py
```

## Pruebas
```bash
pytest
```

## Funcionalidad
- Modelo lógico completo para catálogo, adquisiciones, pesajes, snapshots y análisis con restricciones clave.
- Servicios para seleccionar estado vigente del tirante, K vigente y validación de solapes de instalación.
- Layout Dash con navegación y textos guía para los flujos (catálogo, adquisiciones, pesajes, análisis, histórico y semáforo).
- Documento de arquitectura preliminar en `docs/ARCHITECTURE.md` con la interpretación de la especificación y el modelo de datos.
