from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Dict

from fastapi import FastAPI

from .api import router
from fastapi.responses import JSONResponse

ALGORITHM_VERSION = "v1.0"

app = FastAPI(
    title="CeMPEI Cable Analysis",
    description="API mínima para gestión histórica y análisis de tirantes (etapa 1).",
    version="0.1.0",
)

app.include_router(router)


@app.on_event("startup")
def ensure_data_dirs() -> None:
    data_root = Path(os.environ.get("DATA_ROOT", "/data"))
    for sub in ("raw", "normalized", "attachments"):
        (data_root / sub).mkdir(parents=True, exist_ok=True)


@app.get("/health")
def health() -> Dict[str, Any]:
    return {"status": "ok", "algorithm_version": ALGORITHM_VERSION}


@app.get("/info")
def info() -> Dict[str, Any]:
    return {
        "data_root": os.environ.get("DATA_ROOT", "/data"),
        "database_url": os.environ.get("DATABASE_URL", "postgres://"),
        "notes": "Endpoints de negocio pendientes; esta versión contiene el modelo y lógica base.",
    }


@app.exception_handler(ValueError)
async def value_error_handler(_, exc: ValueError) -> JSONResponse:
    return JSONResponse(status_code=400, content={"detail": str(exc)})
