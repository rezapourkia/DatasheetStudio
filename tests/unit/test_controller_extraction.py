"""Tests for AI extraction validation, acceptance gating, and archiving."""

import json
from pathlib import Path

import pytest

from datasheet_studio.infrastructure.storage.knowledge_index import KnowledgeIndex
from datasheet_studio.infrastructure.storage.knowledge_vault import KnowledgeVault
from datasheet_studio.services.controller_extraction import (
    accepted_profile,
    archive_run,
    build_user_message,
    parse_response,
    run_extraction,
)

HASH = "c" * 64


def field_item(name, value, unit, page=2, **extra):
    item = {"name": name, "value": value, "unit": unit, "page": page}
    item.update(extra)
    return item


def response(fields, **extra):
    payload = {
        "manufacturer": "Linkage",
        "part_number": "DK124",
        "fields": fields,
        "contradictions": [],
        "unknown_facts": [],
    }
    payload.update(extra)
    return json.dumps(payload, ensure_ascii=False)


# --- validation -------------------------------------------------------------


def test_invalid_json_is_reported_not_raised():
    result = parse_response("this is not json at all", 5)
    assert result.ok is False
    assert result.issues[0].code == "invalid-json"


def test_truncated_json_is_detected():
    good = response([field_item("frequency_khz", 65, "kHz")])
    result = parse_response(good[: len(good) // 2], 5)
    assert result.ok is False
    assert result.issues[0].code == "truncation"


def test_missing_unit_and_bad_citation_are_issues():
    text = response(
        [
            field_item("frequency_khz", 65, ""),          # missing unit
            field_item("current_limit_a", 1.1, "A", page=99),  # bad citation
            field_item("switch_voltage_limit_v", 700, "V", page=1),
        ]
    )
    result = parse_response(text, 3)
    assert result.ok is True
    codes = {i.code for i in result.issues}
    assert codes == {"bad-unit", "bad-citation"}
    assert [f["name"] for f in result.candidate_fields] == [
        "switch_voltage_limit_v"
    ]


def test_unknown_field_name_is_rejected():
    text = response([field_item("warp_core", 1, "W", page=1)])
    result = parse_response(text, 3)
    assert result.candidate_fields == []
    assert result.issues[0].code == "bad-field"


# --- run + cancel + provider failure -------------------------------------------

def test_run_with_mock_chat_ok():
    text = response(
        [
            field_item("frequency_khz", 65, "kHz"),
            field_item("current_limit_a", 1.1, "A"),
        ]
    )
    result, request, response_text = run_extraction(
        lambda prompt: text,
        part_number="DK124",
        page_texts={1: "controller description 65kHz"},
        page_count=2,
        source_hash=HASH,
    )
    assert result.ok and len(result.candidate_fields) == 2
    assert "Allowed fields" in request and "page:1" in request
    assert result.run_id


def test_run_cancelled_before_send():
    with pytest.raises(Exception, match="لغو"):
        run_extraction(
            lambda prompt: (_ for _ in ()).throw(AssertionError("must not send")),
            part_number="x",
            page_texts={},
            page_count=1,
            source_hash=HASH,
            should_cancel=lambda: True,
        )


def test_provider_failure_is_wrapped():
    def boom(prompt):
        raise ConnectionError("network down")

    with pytest.raises(Exception, match="AI"):
        run_extraction(
            boom, part_number="x", page_texts={}, page_count=1, source_hash=HASH
        )


# --- acceptance gating -----------------------------------------------------------

def test_only_accepted_fields_enter_profile_and_never_verified():
    result = parse_response(
        response(
            [
                field_item("frequency_khz", 65, "kHz"),
                field_item("current_limit_a", 1.1, "A"),
            ]
        ),
        3,
    )
    profile = accepted_profile(
        result, accepted_names={"frequency_khz"}, source_hash=HASH
    )
    assert [f.name for f in profile.fields] == ["frequency_khz"]
    assert all(f.review_state == "extracted" for f in profile.fields)
    assert profile.fields[0].provenance.extractor_version.startswith("ai:")
    engine = profile.engine_view()
    assert engine.values == {}  # nothing accepted-for-engine yet
    assert "current_limit_a" in engine.unknowns


def test_offline_reuse_saved_profile_loads(tmp_path: Path):
    result = parse_response(
        response([field_item("frequency_khz", 65, "kHz")]), 3
    )
    profile = accepted_profile(
        result, accepted_names={"frequency_khz"}, source_hash=HASH
    )
    vault = KnowledgeVault.create(tmp_path / "vault", "AI Vault")
    vault.mark_accepted()
    target = vault.write_controller_profile(profile)

    from datasheet_studio.models.controller_profile import load_controller_profile

    loaded = load_controller_profile(target.read_text(encoding="utf-8"))
    assert loaded.fields[0].review_state == "extracted"  # reusable offline


def test_archive_run_writes_artifacts(tmp_path: Path):
    result = parse_response(
        response([field_item("frequency_khz", 65, "kHz")]), 3
    )
    folder = archive_run(
        lambda: str(tmp_path),
        run_id="run123",
        request_text="REQ",
        response_text="RESP",
        result=result,
        source_hash=HASH,
        provider="deepseek",
        model="test-model",
    )
    assert folder is not None
    assert (folder / "request.md").read_text(encoding="utf-8") == "REQ"
    meta = json.loads((folder / "metadata.json").read_text(encoding="utf-8"))
    assert meta["prompt_version"].startswith("controller_extraction")
    assert meta["validation_ok"] is True
    assert meta["model"] == "test-model"


def test_build_user_message_lists_allowed_fields_with_units():
    message = build_user_message("DK124", {1: "text"})
    assert "frequency_khz [kHz]" in message
    assert "<!-- page:1 -->" in message
