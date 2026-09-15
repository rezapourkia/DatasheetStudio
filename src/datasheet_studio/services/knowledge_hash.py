"""Content hashing services for the engineering knowledge base.

Streaming SHA-256 keeps memory constant for large PDFs, and canonical record
hashes make record equality reproducible across platforms and key order.
Pure stdlib; no Qt, no network.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

DEFAULT_CHUNK_SIZE = 1 << 20  # 1 MiB


def sha256_bytes(data: bytes) -> str:
    """Return the lowercase SHA-256 hex digest of a bytes payload."""

    return hashlib.sha256(data).hexdigest()


def sha256_file(path: str | Path, chunk_size: int = DEFAULT_CHUNK_SIZE) -> str:
    """Stream a file through SHA-256 without loading it into memory."""

    if chunk_size <= 0:
        raise ValueError("chunk_size must be positive")
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        while True:
            chunk = handle.read(chunk_size)
            if not chunk:
                break
            digest.update(chunk)
    return digest.hexdigest()


def canonical_json(data: Any) -> str:
    """Serialize with sorted keys and compact separators for stable hashing."""

    return json.dumps(data, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def canonical_record_hash(record: object) -> str:
    """SHA-256 over the canonical JSON of a record's ``to_dict`` payload."""

    try:
        payload = record.to_dict()  # type: ignore[attr-defined]
    except AttributeError as exc:
        raise TypeError("record must provide to_dict()") from exc
    return sha256_bytes(canonical_json(payload).encode("utf-8"))
