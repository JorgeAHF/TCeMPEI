import hashlib
from pathlib import Path
from typing import BinaryIO, Tuple


def sha256_for_fileobj(fobj: BinaryIO, chunk_size: int = 8192) -> str:
    hasher = hashlib.sha256()
    while True:
        chunk = fobj.read(chunk_size)
        if not chunk:
            break
        hasher.update(chunk)
    return hasher.hexdigest()


def save_upload(base_dir: Path, subdir: str, filename: str, data: bytes) -> Tuple[Path, str]:
    target_dir = base_dir / subdir
    target_dir.mkdir(parents=True, exist_ok=True)
    path = target_dir / filename
    path.write_bytes(data)
    digest = hashlib.sha256(data).hexdigest()
    return path, digest
