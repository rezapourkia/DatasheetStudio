"""Tests for streaming and canonical hashing services."""

import hashlib
import json
from pathlib import Path

import pytest

from datasheet_studio.services.knowledge_hash import (
    canonical_json,
    canonical_record_hash,
    sha256_bytes,
    sha256_file,
)
from datasheet_studio.models.knowledge_base import EvidenceField, Provenance


def test_sha256_bytes_known_vectors() -> None:
    assert (
        sha256_bytes(b"")
        == "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"
    )
    assert (
        sha256_bytes(b"abc")
        == "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad"
    )


def test_sha256_file_streams_in_chunks(tmp_path: Path) -> None:
    payload = (b"0123456789abcdef" * 131_072)[:5_000_003]  # ~5 MB, odd length
    path = tmp_path / "big.pdf"
    path.write_bytes(payload)
    assert sha256_file(path, chunk_size=4096) == hashlib.sha256(payload).hexdigest()
    assert sha256_file(path) == hashlib.sha256(payload).hexdigest()


def test_sha256_file_rejects_bad_chunk_size(tmp_path: Path) -> None:
    path = tmp_path / "empty.bin"
    path.write_bytes(b"")
    with pytest.raises(ValueError):
        sha256_file(path, chunk_size=0)


def test_canonical_json_is_key_order_independent() -> None:
    first = {"b": 1, "a": {"d": 2, "c": [3, {"z": 4, "y": 5}]}}
    second = {"a": {"c": [3, {"y": 5, "z": 4}], "d": 2}, "b": 1}
    assert canonical_json(first) == canonical_json(second)


def test_canonical_record_hash_is_stable_across_load_order() -> None:
    payload = {
        "name": "current_limit_a",
        "value": 1.1,
        "unit": "A",
        "provenance": {"source_hash": "a" * 64, "page": 2},
    }
    reordered = {
        "provenance": {"page": 2, "source_hash": "a" * 64},
        "unit": "A",
        "value": 1.1,
        "name": "current_limit_a",
    }
    first = EvidenceField.from_dict(payload)
    second = EvidenceField.from_dict(reordered)
    assert first == second
    assert canonical_record_hash(first) == canonical_record_hash(second)
    assert json.loads(canonical_json(first.to_dict())) == first.to_dict()
