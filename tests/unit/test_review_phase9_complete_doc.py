"""Review P1/Phase 9: extraction must read the complete document."""

import json
from pathlib import Path

import pytest

from datasheet_studio.services.controller_extraction import (
    build_user_message,
    chunk_plan,
    extract_complete,
)


def _chat_returning(fields_by_page):
    """Fake provider: each chunk returns one field citing its own page."""

    calls = []

    def chat(prompt: str) -> str:
        calls.append(prompt)
        pages = [
            int(marker.split(":")[1].split()[0])
            for marker in prompt.splitlines()
            if marker.startswith("<!-- page:")
        ]
        payload = {
            "manufacturer": "Linkage",
            "part_number": "DK124",
            "fields": [
                {
                    "name": name,
                    "value": value,
                    "unit": unit,
                    "page": page,
                }
                for page in pages
                for name, value, unit in fields_by_page.get(page, [])
            ],
            "contradictions": [],
            "unknown_facts": [],
        }
        return json.dumps(payload, ensure_ascii=False)

    chat.calls = calls
    return chat


def test_user_message_never_drops_pages_or_truncates_text():
    pages = {number: f"unique-marker-{number} " * 30 for number in range(1, 51)}
    message = build_user_message("DK124", pages, chunk_pages=10, chunk_index=1)
    # The FIRST chunk message must contain its own pages fully…
    assert "<!-- page:1 -->" in message and "unique-marker-1" in message
    # …and no page is silently lost across the whole plan.
    plan = chunk_plan(pages, chunk_pages=10)
    assert len(plan) == 5
    covered = [page for _index, pages_in_chunk in plan for page in pages_in_chunk]
    assert covered == list(range(1, 51))


def test_extract_complete_accounts_for_every_page_and_reports_omitted():
    coverage_pages = {1: "text", 2: "text", 3: ""}  # page 3 empty→scanned
    result = extract_complete(
        _chat_returning({1: [("frequency_khz", 65.0, "kHz")]}),
        part_number="DK124",
        page_texts=coverage_pages,
        complete_pages=(1, 2),  # ledger says 3 is not extractable
        page_count=3,
        source_hash="a" * 64,
    )
    assert result.result.ok
    assert result.omitted_pages == [3]
    assert result.complete is False  # a complete claim is blocked


def test_extract_complete_merges_chunks_and_detects_contradictions():
    def chat(prompt: str) -> str:
        page = 1 if "page:1 -->" in prompt else 2
        value = 65.0 if page == 1 else 70.0  # same field, conflicting value
        return json.dumps(
            {
                "manufacturer": "Linkage",
                "part_number": "DK124",
                "fields": [
                    {"name": "frequency_khz", "value": value,
                     "unit": "kHz", "page": page}
                ],
                "contradictions": [],
                "unknown_facts": [],
            },
            ensure_ascii=False,
        )

    result = extract_complete(
        chat,
        part_number="DK124",
        page_texts={1: "a", 2: "b"},
        complete_pages=(1, 2),
        page_count=2,
        source_hash="a" * 64,
        chunk_pages=1,  # separate chunks so each cites its own page
    )
    assert result.complete is True
    names = [f["name"] for f in result.result.candidate_fields]
    assert names == ["frequency_khz"]  # merged to ONE deterministic value
    assert any(
        "frequency_khz" in c and ("65" in c and "70" in c)
        for c in result.result.contradictions
    )


def test_extract_complete_archives_every_chunk_and_merge(tmp_path: Path):
    chat = _chat_returning({1: [("frequency_khz", 65.0, "kHz")]})
    result = extract_complete(
        chat,
        part_number="DK124",
        page_texts={1: "a", 2: "b"},
        complete_pages=(1, 2),
        page_count=2,
        source_hash="a" * 64,
        chunk_pages=1,  # force one page per chunk → two archived chunks
        archive_root=tmp_path,
    )
    run_dir = tmp_path / result.result.run_id
    chunks = sorted((run_dir / "chunks").iterdir())
    assert [c.name for c in chunks] == ["chunk-1", "chunk-2"]
    for chunk in chunks:
        assert (chunk / "request.md").is_file()
        assert (chunk / "response.md").is_file()
    assert (run_dir / "merge.md").is_file()
    meta = json.loads((run_dir / "metadata.json").read_text(encoding="utf-8"))
    assert meta["chunks"] == 2 and meta["complete"] is True
    assert meta["omitted_pages"] == []
