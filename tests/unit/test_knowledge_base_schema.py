"""Schema tests for the Phase 2 knowledge-base domain types."""

import json
from pathlib import Path

import pytest

from datasheet_studio.models.knowledge_base import (
    SCHEMA_VERSION,
    Alias,
    ComponentProfile,
    DocumentRevision,
    EvidenceField,
    KnowledgeBaseVersionError,
    LibraryIdentity,
    MagneticsRecord,
    Provenance,
    RecordValidationError,
    SourceObject,
    dump_library_identity,
    dump_record,
    is_automated_assignable,
    load_library_identity,
    load_record,
    validate_relative_path,
)

FIXTURES = Path(__file__).parent.parent / "fixtures" / "knowledge_base"

SOURCE_HASH = "a" * 64


def make_field(**overrides) -> EvidenceField:
    data = dict(
        name="current_limit_a",
        value=1.1,
        unit="A",
        provenance=Provenance(source_hash=SOURCE_HASH, page=2),
    )
    data.update(overrides)
    return EvidenceField(**data)


# --- round-trip -----------------------------------------------------------


@pytest.mark.parametrize(
    "fixture_name",
    [
        "source_object.json",
        "document_revision.json",
        "dk124_profile.json",
        "ee19_core_record.json",
    ],
)
def test_fixture_round_trip_is_lossless(fixture_name: str) -> None:
    text = (FIXTURES / fixture_name).read_text(encoding="utf-8")
    record = load_record(text)
    envelope = json.loads(dump_record(record))
    assert envelope == json.loads(text)


def test_library_identity_round_trip() -> None:
    identity = LibraryIdentity(
        library_id="0f1e2d3c4b5a69788796a5b4c3d2e1f0",
        name="کتابخانه مهندسی من",
        created_at="2026-09-15T10:00:00Z",
    )
    assert identity.created_at == "2026-09-15T10:00:00+00:00"
    loaded = load_library_identity(dump_library_identity(identity))
    assert loaded == identity


# --- example records for the owner review gate -----------------------------


def test_dk124_example_profile_is_never_verified() -> None:
    profile = load_record((FIXTURES / "dk124_profile.json").read_text(encoding="utf-8"))
    assert isinstance(profile, ComponentProfile)
    assert profile.fields
    assert all(field.review_state != "verified" for field in profile.fields)


def test_ee19_example_core_record_is_never_verified() -> None:
    record = load_record((FIXTURES / "ee19_core_record.json").read_text(encoding="utf-8"))
    assert isinstance(record, MagneticsRecord)
    assert record.family == "EE19/17"
    assert record.fields
    assert all(field.review_state != "verified" for field in record.fields)


# --- invalid schema rejection ----------------------------------------------


def test_unknown_keys_are_rejected() -> None:
    payload = {
        "sha256": SOURCE_HASH,
        "size_bytes": 10,
        "media_type": "application/pdf",
        "original_filename": "a.pdf",
        "surprise": True,
    }
    with pytest.raises(RecordValidationError, match="surprise"):
        SourceObject.from_dict(payload)


def test_bad_review_state_is_rejected() -> None:
    with pytest.raises(RecordValidationError):
        make_field(review_state="blessed")


def test_verified_without_reviewer_is_rejected() -> None:
    with pytest.raises(RecordValidationError, match="verified"):
        make_field(review_state="verified")


def test_reviewer_on_unreviewed_state_is_rejected() -> None:
    with pytest.raises(RecordValidationError):
        make_field(reviewed_by="Reza")


def test_verified_with_reviewer_and_timestamp_is_accepted() -> None:
    field = make_field(
        review_state="verified",
        reviewed_by="Reza",
        reviewed_at="2026-09-15T09:00:00+00:00",
    )
    assert field.is_human_verified


def test_malformed_source_hash_is_rejected() -> None:
    with pytest.raises(RecordValidationError):
        Provenance(source_hash="XYZ")


def test_page_must_be_positive() -> None:
    with pytest.raises(RecordValidationError):
        Provenance(source_hash=SOURCE_HASH, page=0)


def test_confidence_bounds_are_enforced() -> None:
    with pytest.raises(RecordValidationError):
        Provenance(source_hash=SOURCE_HASH, confidence=1.5)


def test_bad_iso_datetime_is_rejected() -> None:
    with pytest.raises(RecordValidationError):
        Provenance(source_hash=SOURCE_HASH, imported_at="15/09/2026")


def test_min_typ_max_order_is_enforced() -> None:
    with pytest.raises(RecordValidationError):
        make_field(value_min=2.0, value_typ=1.0, value_max=3.0)


def test_duplicate_field_names_are_rejected() -> None:
    field = make_field()
    with pytest.raises(RecordValidationError):
        ComponentProfile(
            manufacturer="M",
            part_number="P",
            profile_version="1",
            source_object_sha256=SOURCE_HASH,
            fields=(field, field),
        )


def test_duplicate_tags_are_rejected() -> None:
    with pytest.raises(RecordValidationError):
        DocumentRevision(
            manufacturer="M",
            part_number="P",
            document_type="datasheet",
            revision="1",
            object_sha256=SOURCE_HASH,
            record_path="records/datasheets/m/p/1/record.md",
            tags=("power", "power"),
        )


def test_bad_alias_kind_is_rejected() -> None:
    with pytest.raises(RecordValidationError):
        Alias("X", "nickname")


def test_filename_path_is_rejected() -> None:
    with pytest.raises(RecordValidationError):
        SourceObject(
            sha256=SOURCE_HASH,
            size_bytes=1,
            media_type="application/pdf",
            original_filename="folder/file.pdf",
        )


# --- path safety ------------------------------------------------------------


@pytest.mark.parametrize(
    "path",
    [
        "C:/records/a.md",
        "/records/a.md",
        "records/../records/a.md",
        "records//a.md",
        "records/./a.md",
        r"records\a.md",
        "outside/a.md",
    ],
)
def test_unsafe_paths_are_rejected(path: str) -> None:
    with pytest.raises(RecordValidationError):
        validate_relative_path(path)


def test_valid_relative_path_is_accepted() -> None:
    assert (
        validate_relative_path("records/datasheets/linkage/DK124/v1.6/record.md")
        == "records/datasheets/linkage/DK124/v1.6/record.md"
    )


# --- duplicate identity ------------------------------------------------------


def make_source(**overrides) -> SourceObject:
    data = dict(
        sha256=SOURCE_HASH,
        size_bytes=100,
        media_type="application/pdf",
        original_filename="a.pdf",
        source_urls=("https://x.invalid/a",),
        aliases=(Alias("A1", "part-number"),),
    )
    data.update(overrides)
    return SourceObject(**data)


def test_merge_unions_urls_and_aliases_in_first_seen_order() -> None:
    first = make_source()
    second = make_source(
        original_filename="b.pdf",
        source_urls=("https://x.invalid/b", "https://x.invalid/a"),
        aliases=(Alias("B1", "oem"), Alias("A1", "part-number", "duplicate")),
    )
    merged = first.merged(second)
    assert merged.source_urls == (
        "https://x.invalid/a",
        "https://x.invalid/b",
    )
    assert [alias.value for alias in merged.aliases] == ["A1", "B1"]
    assert merged.aliases[0].note == "duplicate"
    assert merged.original_filename == "a.pdf"


def test_merge_rejects_mismatched_hash_and_size() -> None:
    with pytest.raises(RecordValidationError):
        make_source().merged(make_source(sha256="b" * 64))
    with pytest.raises(RecordValidationError):
        make_source().merged(make_source(size_bytes=101))


# --- version upgrade ----------------------------------------------------------


def test_legacy_v1_envelope_is_rejected_with_version_error() -> None:
    text = (FIXTURES / "legacy_v1_record.json").read_text(encoding="utf-8")
    with pytest.raises(KnowledgeBaseVersionError):
        load_record(text)


def test_future_schema_version_is_rejected() -> None:
    envelope = {
        "schema_version": SCHEMA_VERSION + 1,
        "record_kind": "source-object",
        "record": {},
    }
    with pytest.raises(KnowledgeBaseVersionError):
        load_record(envelope)


def test_library_identity_version_is_enforced() -> None:
    with pytest.raises(KnowledgeBaseVersionError):
        LibraryIdentity(
            library_id="0f1e2d3c4b5a69788796a5b4c3d2e1f0",
            name="x",
            created_at="2026-09-15T10:00:00+00:00",
            schema_version=1,
        )


# --- automated review-state cap -------------------------------------------------


@pytest.mark.parametrize("state", ["unreviewed", "extracted"])
def test_automated_states_are_assignable(state: str) -> None:
    assert is_automated_assignable(state)


@pytest.mark.parametrize("state", ["reviewed", "verified", "rejected"])
def test_human_states_are_not_automatically_assignable(state: str) -> None:
    assert not is_automated_assignable(state)
