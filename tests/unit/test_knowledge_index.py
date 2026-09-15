"""Tests for the rebuildable SQLite/FTS5 knowledge-base index."""

import sqlite3
import time

import pytest

from datasheet_studio.infrastructure.storage.knowledge_index import (
    IndexCorruptError,
    KnowledgeIndex,
    parse_query,
)
from datasheet_studio.models.knowledge_base import (
    Alias,
    ComponentProfile,
    DocumentRevision,
    EvidenceField,
    MagneticsRecord,
    Provenance,
    SourceObject,
)

DK_HASH = "b" * 64
EE_HASH = "c" * 64
PAGE_HASH = "d" * 64


def field(name, value, unit="", *, review="extracted", page=2, source=DK_HASH):
    extra = {}
    if review == "verified":
        extra = {"reviewed_by": "Reza", "reviewed_at": "2026-09-15T09:00:00+00:00"}
    return EvidenceField(
        name=name,
        value=value,
        unit=unit,
        provenance=Provenance(
            source_hash=source, page=page, extractor_version="test"
        ),
        review_state=review,
        **extra,
    )


def dk_document(**overrides) -> DocumentRevision:
    data = dict(
        manufacturer="Linkage",
        part_number="DK124",
        document_type="datasheet",
        revision="v1.6",
        object_sha256=DK_HASH,
        record_path="records/datasheets/linkage/DK124/v1.6/record.md",
        title="DK124 offline switching controller",
        summary=" offline flyback switcher with 700V transistor ",
        tags=("flyback", "controller"),
        aliases=(Alias("DK124B", "ordering-code"),),
        fields=(field("current_limit_a", 1.1, "A"),),
    )
    data.update(overrides)
    return DocumentRevision(**data)


def dk_profile(**overrides) -> ComponentProfile:
    data = dict(
        manufacturer="Linkage",
        part_number="DK124",
        profile_version="0.1",
        source_object_sha256=DK_HASH,
        device_type="offline-switching-controller",
        fields=(field("switching_frequency_khz", 65, "kHz"),),
    )
    data.update(overrides)
    return ComponentProfile(**data)


def ee_core() -> MagneticsRecord:
    return MagneticsRecord(
        manufacturer="TDK-illustrative",
        family="EE19/17",
        kind="core",
        designation="EE19-17-ILLUSTRATIVE",
        fields=(field("effective_area_ae_mm2", 23.0, "mm²", source=EE_HASH),),
    )


def sample_records():
    return [dk_document(), dk_profile(), ee_core()]


def sample_pages():
    return [
        (PAGE_HASH, 1, "Absolute maximum ratings: collector-emitter voltage 700V"),
        (PAGE_HASH, 2, "Electrical characteristics: current limit 1.1A typical, 65kHz fixed frequency"),
    ]


@pytest.fixture()
def index(tmp_path):
    with KnowledgeIndex.open(tmp_path / "library.sqlite") as ix:
        ix.rebuild(sample_records(), sample_pages())
        yield ix


# --- lifecycle ---------------------------------------------------------------


def test_open_corrupt_file_raises(tmp_path):
    path = tmp_path / "broken.sqlite"
    path.write_bytes(b"this is definitely not a sqlite database")
    with pytest.raises(IndexCorruptError):
        KnowledgeIndex.open(path)


def test_recover_rebuilds_from_garbage_file(tmp_path):
    path = tmp_path / "broken.sqlite"
    path.write_bytes(b"garbage" * 100)
    with KnowledgeIndex.recover(path, sample_records(), sample_pages()) as ix:
        assert ix.stats().documents == 1
        hits = ix.search("DK124")
        assert any(h.kind == "document" for h in hits)


def test_rebuild_is_atomic_and_equivalent(tmp_path):
    path = tmp_path / "library.sqlite"
    with KnowledgeIndex.open(path) as ix:
        stats = ix.rebuild(sample_records(), sample_pages())
        assert stats.documents == 1 and stats.components == 1 and stats.magnetics == 1
        first = ix.search("dk1 controller", limit=50)
        pages_first = ix.search("maximum 700V", limit=50)
        assert first
    # delete the index entirely and rebuild from the same records
    path.unlink()
    with KnowledgeIndex.open(path) as ix:
        ix.rebuild(sample_records(), sample_pages())
        assert ix.search("dk1 controller", limit=50) == first
        assert ix.search("maximum 700V", limit=50) == pages_first


def test_transaction_rollback_on_failure(tmp_path):
    with KnowledgeIndex.open(tmp_path / "ix.sqlite") as ix:
        ix.rebuild(sample_records(), sample_pages())
        with pytest.raises(sqlite3.IntegrityError):
            with ix.transaction():
                ix._conn.execute(
                    "INSERT INTO documents(record_path) VALUES('records/a')"
                )
                ix._conn.execute(
                    "INSERT INTO documents(record_path) VALUES('records/a')"
                )
        assert ix.stats().documents == 1  # rolled back, not 2


def test_upsert_and_remove_document(index):
    assert index.stats().documents == 1
    index.remove_document(dk_document().record_path)
    assert index.stats().documents == 0
    assert index.search("DK124", kinds=("document",)) == []


def test_upsert_replaces_existing_document(index):
    changed = dk_document(title="DK124 revised title", summary="new summary text")
    index.upsert_document(changed)
    assert index.stats().documents == 1
    titles = [h.title for h in index.search("revised", kinds=("document",))]
    assert titles == ["DK124 revised title"]


def test_integrity_check(index):
    assert index.check_integrity()


# --- query grammar ------------------------------------------------------------


def test_parse_query_splits_filters_and_terms():
    filters, terms = parse_query("maker:linkage type:datasheet DK 124 junk:x word")
    assert filters == {"maker": "linkage", "type": "datasheet"}
    # whitespace tokens only; unknown filter keys stay ordinary terms
    assert terms == ["DK", "124", "junk:x", "word"]


def test_free_term_prefix_matches_part_number(index):
    hits = index.search("dk1")
    assert any(h.kind == "document" and "DK124" in h.title for h in hits)


def test_maker_filter(index):
    hits = index.search("maker:linkage dk1", kinds=("document",))
    assert hits
    assert all("Linkage" in h.subtitle for h in hits)


def test_type_filter_exact(index):
    hits = index.search("type:datasheet")
    assert any(h.kind == "document" for h in hits)
    assert not any(
        h.kind == "document" and "errata" in h.subtitle.lower() for h in hits
    )


def test_core_filter_matches_family(index):
    hits = index.search("core:ee19", kinds=("magnetics",))
    assert [h.kind for h in hits] == ["magnetics"]
    assert "EE19/17" in hits[0].title


def test_verified_filter_on_fields(index):
    index.upsert_document(
        dk_document(
            fields=(
                field("current_limit_a", 1.1, "A"),
                field("ovp_threshold_v", 540, "V", review="verified"),
            ),
            record_path="records/datasheets/linkage/DK124/v2/record.md",
        )
    )
    yes = index.search("verified:yes", kinds=("field",))
    no = index.search("verified:no", kinds=("field",))
    assert [h.title.split(" =")[0] for h in yes] == ["ovp_threshold_v"]
    assert all("ovp_threshold_v" not in h.title for h in no)


def test_field_hit_identifies_owner_and_state(index):
    hits = index.search("current_limit", kinds=("field",))
    assert hits
    hit = hits[0]
    assert hit.ref["owner_table"] == "documents"
    assert "extracted" in hit.subtitle
    assert "«" in hit.snippet


def test_page_hit_returns_page_number_and_snippet(index):
    hits = index.search("700V", kinds=("page",))
    assert hits
    assert hits[0].kind == "page"
    assert hits[0].ref["page"] == 1
    assert "«700V»" in hits[0].snippet


def test_component_hit_by_free_text(index):
    hits = index.search("DK124", kinds=("component",))
    assert hits and hits[0].kind == "component"
    assert hits[0].subtitle == "پروفایل 0.1"


def test_search_results_are_deterministic(index):
    assert index.search("DK124") == index.search("DK124")


def test_persian_free_text_searches_documents(index):
    doc = dk_document(
        summary="منبع تغذیه سوئیچینگ با کلید داخلی ۷۰۰ ولتی",
        record_path="records/datasheets/linkage/DK124/vfa/record.md",
    )
    index.upsert_document(doc)
    hits = index.search("ولتی")
    assert any(h.kind == "document" for h in hits)


# --- performance ---------------------------------------------------------------


def test_large_synthetic_library_performance(tmp_path):
    docs, pages = [], []
    makers = ("ST", "TI", "Linkage", "Maxim", "onsemi")
    for i in range(1500):
        maker = makers[i % len(makers)]
        part = f"PART{i:05d}"
        docs.append(
            DocumentRevision(
                manufacturer=maker,
                part_number=part,
                document_type="datasheet",
                revision="rev1",
                object_sha256=f"{i:064x}",
                record_path=f"records/datasheets/{maker.lower()}/{part}/rev1/record.md",
                title=f"{part} switching regulator datasheet",
                summary="high efficiency synchronous buck regulator with 600V rating",
                tags=("power", "buck"),
                fields=(
                    field("switching_frequency_khz", 65.0 + i, "kHz", source=f"{i:064x}"),
                    field("current_limit_a", 1.0 + (i % 50) / 10, "A", source=f"{i:064x}"),
                    field("material_grade", "PC40" if i % 2 else "N87", source=f"{i:064x}"),
                    field("esr_ohm", 0.08, "Ω", source=f"{i:064x}"),
                ),
            )
        )
        pages.append((f"{i:064x}", 1, f"{part} absolute maximum ratings 600V page one text"))
        pages.append((f"{i:064x}", 2, f"{part} electrical characteristics current limit typical value"))
    path = tmp_path / "big.sqlite"
    start = time.perf_counter()
    with KnowledgeIndex.open(path) as ix:
        build_stats = ix.rebuild(docs, pages)
        build_seconds = time.perf_counter() - start
        query_start = time.perf_counter()
        hits_part = ix.search("PART00042")
        query_1 = time.perf_counter() - query_start
        query_start = time.perf_counter()
        hits_filter = ix.search("maker:ti material:PC40", kinds=("field",))
        query_2 = time.perf_counter() - query_start
        query_start = time.perf_counter()
        hits_page = ix.search("maximum 600V", kinds=("page",))
        query_3 = time.perf_counter() - query_start
        assert build_stats.documents == 1500
        assert build_stats.fields == 6000
        assert build_stats.pages == 3000
        assert hits_part, "part-number query must find the document"
        assert hits_filter, "field filter query must find material fields"
        assert hits_page, "page query must find page text"
    print(
        f"\nPERF build={build_seconds:.2f}s q_part={query_1:.3f}s "
        f"q_filter={query_2:.3f}s q_page={query_3:.3f}s"
    )
    assert build_seconds < 90
    assert max(query_1, query_2, query_3) < 2.0
