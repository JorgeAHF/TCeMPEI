import sys
from pathlib import Path


# Garantiza que el paquete app esté disponible durante las pruebas.
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

