"""Artifact storage abstraction (LocalStorage shipped; S3/Azure Blob later)."""
from __future__ import annotations

import logging
import re
import shutil
from pathlib import Path
from typing import Protocol

from app.config import settings
from app.core.errors import NotFoundError

logger = logging.getLogger("app.storage")


class ArtifactStorage(Protocol):
    async def save(self, *, key: str, data: bytes) -> str: ...

    async def get(self, key: str) -> bytes: ...

    async def delete(self, key: str) -> None: ...

    async def exists(self, key: str) -> bool: ...


_SAFE_PATH = re.compile(r"[^A-Za-z0-9_./-]")


def _normalize_key(key: str) -> str:
    key = key.replace("\\", "/").lstrip("/")
    cleaned = _SAFE_PATH.sub("_", key)
    if ".." in cleaned.split("/"):
        raise ValueError("illegal artifact path")
    return cleaned


class LocalStorage:
    def __init__(self, root: str | None = None):
        self._root = Path(root or settings.storage_local_root)

    async def save(self, *, key: str, data: bytes) -> str:
        key = _normalize_key(key)
        dest = self._root / key
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(data)
        return f"/artifacts/{key}"

    async def get(self, key: str) -> bytes:
        key = _normalize_key(key)
        dest = self._root / key
        if not dest.is_file():
            raise NotFoundError(f"artifact not found: {key}")
        return dest.read_bytes()

    async def delete(self, key: str) -> None:
        key = _normalize_key(key)
        dest = self._root / key
        if dest.exists():
            if dest.is_dir():
                shutil.rmtree(dest)
            else:
                dest.unlink()

    async def exists(self, key: str) -> bool:
        return (self._root / _normalize_key(key)).exists()

    def path_for(self, key: str) -> Path:
        return self._root / _normalize_key(key)


storage = LocalStorage()
