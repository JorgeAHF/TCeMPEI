import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = Path(os.getenv("DATA_DIR", BASE_DIR / "data"))
RAW_DIR = DATA_DIR / "raw"
NORMALIZED_DIR = DATA_DIR / "normalized"
ATTACHMENTS_DIR = DATA_DIR / "attachments"

DATABASE_URL = os.getenv(
    "DATABASE_URL", "sqlite+sqlite:///" + str(BASE_DIR / "tcempei.db")
)
ALGORITHM_VERSION = "1.0.0"

def ensure_data_dirs() -> None:
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    NORMALIZED_DIR.mkdir(parents=True, exist_ok=True)
    ATTACHMENTS_DIR.mkdir(parents=True, exist_ok=True)

