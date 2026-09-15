"""Rebuildable SQLite/FTS5 index over knowledge-base records.

The durable truth stays in the portable record files (ADR-019); this index
only accelerates search and can be deleted and rebuilt at any time.  All
writes go through this adapter — each record kind owns its FTS table and the
FTS rowid always equals the owning table's rowid, so no triggers are needed.

Synchronous, single-connection.  The UI must call ``rebuild``/``search``
from a worker thread (see ``docs/modules/KNOWLEDGE_INDEX.md`` §2).
"""

from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass
import os
from pathlib import Path
import sqlite3
from typing import Iterable, Sequence

from datasheet_studio.models.knowledge_base import (
    ComponentProfile,
    DocumentRevision,
    MagneticsRecord,
    SourceObject,
)

INDEX_VERSION = "1"

_SCHEMA = """
CREATE TABLE IF NOT EXISTS meta(
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS sources(
    sha256 TEXT PRIMARY KEY,
    size_bytes INTEGER NOT NULL,
    media_type TEXT NOT NULL,
    original_filename TEXT NOT NULL,
    imported_at TEXT NOT NULL DEFAULT ''
);
CREATE TABLE IF NOT EXISTS documents(
    id INTEGER PRIMARY KEY,
    manufacturer TEXT NOT NULL,
    part_number TEXT NOT NULL,
    document_type TEXT NOT NULL,
    revision TEXT NOT NULL,
    object_sha256 TEXT NOT NULL,
    record_path TEXT NOT NULL UNIQUE,
    title TEXT NOT NULL DEFAULT '',
    date TEXT NOT NULL DEFAULT '',
    page_count INTEGER,
    summary TEXT NOT NULL DEFAULT ''
);
CREATE TABLE IF NOT EXISTS components(
    id INTEGER PRIMARY KEY,
    manufacturer TEXT NOT NULL,
    part_number TEXT NOT NULL,
    profile_version TEXT NOT NULL,
    source_object_sha256 TEXT NOT NULL DEFAULT '',
    device_type TEXT NOT NULL DEFAULT '',
    package TEXT NOT NULL DEFAULT '',
    UNIQUE(manufacturer, part_number, profile_version)
);
CREATE TABLE IF NOT EXISTS magnetics(
    id INTEGER PRIMARY KEY,
    manufacturer TEXT NOT NULL,
    family TEXT NOT NULL,
    kind TEXT NOT NULL,
    designation TEXT NOT NULL,
    UNIQUE(manufacturer, family, kind, designation)
);
CREATE TABLE IF NOT EXISTS aliases(
    id INTEGER PRIMARY KEY,
    owner_table TEXT NOT NULL,
    owner_id INTEGER NOT NULL,
    value TEXT NOT NULL,
    kind TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS tags(
    owner_table TEXT NOT NULL,
    owner_id INTEGER NOT NULL,
    tag TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS fields(
    id INTEGER PRIMARY KEY,
    owner_table TEXT NOT NULL,
    owner_id INTEGER NOT NULL,
    name TEXT NOT NULL,
    unit TEXT NOT NULL DEFAULT '',
    value_text TEXT,
    value_num REAL,
    value_min REAL,
    value_typ REAL,
    value_max REAL,
    review_state TEXT NOT NULL,
    source_hash TEXT NOT NULL DEFAULT '',
    page INTEGER,
    conditions TEXT NOT NULL DEFAULT ''
);
CREATE TABLE IF NOT EXISTS page_texts(
    rowid_alias INTEGER PRIMARY KEY,
    source_hash TEXT NOT NULL,
    page INTEGER NOT NULL,
    text TEXT NOT NULL,
    UNIQUE(source_hash, page)
);
CREATE VIRTUAL TABLE IF NOT EXISTS fts_docs USING fts5(content, tokenize='unicode61');
CREATE VIRTUAL TABLE IF NOT EXISTS fts_components USING fts5(content, tokenize='unicode61');
CREATE VIRTUAL TABLE IF NOT EXISTS fts_magnetics USING fts5(content, tokenize='unicode61');
CREATE VIRTUAL TABLE IF NOT EXISTS fts_fields USING fts5(content, tokenize='unicode61');
CREATE VIRTUAL TABLE IF NOT EXISTS fts_pages USING fts5(content, tokenize='unicode61');
"""

# FTS table per record kind; rowid == owning table's rowid (no collisions).
_OWNER_FTS = {
    "documents": "fts_docs",
    "components": "fts_components",
    "magnetics": "fts_magnetics",
}


class IndexCorruptError(RuntimeError):
    """The index file is not a usable database and must be recovered."""


@dataclass(frozen=True)
class SearchHit:
    """One ranked search result with identifying context."""

    kind: str  # document | component | magnetics | field | page
    title: str
    subtitle: str
    snippet: str
    ref: dict[str, object]
    rank: float


@dataclass(frozen=True)
class IndexStats:
    documents: int
    components: int
    magnetics: int
    fields: int
    pages: int
    sources: int


_FILTER_KEYS = {"maker", "type", "core", "material", "verified"}
_KIND_ORDER = ("document", "component", "magnetics", "field", "page")


def parse_query(query: str) -> tuple[dict[str, str], list[str]]:
    """Split a search string into ``filter:value`` filters and free terms."""

    filters: dict[str, str] = {}
    terms: list[str] = []
    for token in query.split():
        key, sep, value = token.partition(":")
        if sep and key.casefold() in _FILTER_KEYS and value:
            filters[key.casefold()] = value.strip("\"'")
        else:
            terms.append(token.strip("\"'"))
    return filters, terms


def _fts_match(terms: Sequence[str]) -> str | None:
    """Build an FTS5 prefix-AND match expression from free terms."""

    parts = []
    for term in terms:
        for piece in term.replace('"', " ").split():
            parts.append(f'"{piece}"*')
    return " AND ".join(parts) if parts else None


def _field_owner_title(conn: sqlite3.Connection, table: str, owner_id: int) -> tuple[str, str]:
    if table == "documents":
        row = conn.execute(
            "SELECT manufacturer, part_number, revision FROM documents WHERE id=?",
            (owner_id,),
        ).fetchone()
        if row:
            return f"{row[0]} {row[1]}", f"سند {row[2]}"
    elif table == "components":
        row = conn.execute(
            "SELECT manufacturer, part_number, profile_version FROM components WHERE id=?",
            (owner_id,),
        ).fetchone()
        if row:
            return f"{row[0]} {row[1]}", f"پروفایل {row[2]}"
    elif table == "magnetics":
        row = conn.execute(
            "SELECT family, designation FROM magnetics WHERE id=?",
            (owner_id,),
        ).fetchone()
        if row:
            return str(row[0]), str(row[1])
    return "؟", "؟"


def _field_search_text(name: str, unit: str, value_text: str | None,
                       value_num: float | None, conditions: str) -> str:
    pieces = [name, unit, conditions or ""]
    if value_text:
        pieces.append(str(value_text))
    if value_num is not None:
        pieces.append(f"{value_num:g}")
    return " ".join(piece for piece in pieces if piece)


class KnowledgeIndex:
    """SQLite/FTS5 search index; rebuildable, never the sole copy of data."""

    def __init__(self, path: str | Path) -> None:
        self._path = Path(path)
        self._conn = sqlite3.connect(str(self._path), isolation_level=None)
        try:
            self._conn.executescript(_SCHEMA)
            self._conn.execute(
                "INSERT OR IGNORE INTO meta(key, value) VALUES('index_version', ?)",
                (INDEX_VERSION,),
            )
        except sqlite3.DatabaseError as exc:
            self._conn.close()
            raise IndexCorruptError(f"ایندکس قابل استفاده نیست: {exc}") from exc

    # -- lifecycle ----------------------------------------------------------

    @classmethod
    def open(cls, path: str | Path) -> "KnowledgeIndex":
        try:
            return cls(path)
        except sqlite3.DatabaseError as exc:
            raise IndexCorruptError(str(exc)) from exc

    def close(self) -> None:
        self._conn.close()

    def __enter__(self) -> "KnowledgeIndex":
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()

    @classmethod
    def recover(
        cls,
        path: str | Path,
        records: Iterable[object] = (),
        page_texts: Iterable[tuple[str, int, str]] = (),
    ) -> "KnowledgeIndex":
        """Delete a corrupt index file and rebuild it from scratch."""

        path = Path(path)
        for suffix in ("", "-wal", "-shm"):
            candidate = Path(str(path) + suffix)
            if candidate.exists():
                candidate.unlink()
        return cls._build_atomic(path, records, page_texts)

    # -- transactions --------------------------------------------------------

    @contextmanager
    def transaction(self):
        self._conn.execute("BEGIN IMMEDIATE")
        try:
            yield self
        except BaseException:
            self._conn.execute("ROLLBACK")
            raise
        else:
            self._conn.execute("COMMIT")

    # -- writes ---------------------------------------------------------------

    def upsert_source(self, source: SourceObject) -> None:
        with self.transaction():
            self._write_source(source)

    def _write_source(self, source: SourceObject) -> None:
        self._conn.execute(
            "INSERT INTO sources(sha256, size_bytes, media_type, original_filename, imported_at)"
            " VALUES(?,?,?,?,?)"
            " ON CONFLICT(sha256) DO UPDATE SET size_bytes=excluded.size_bytes,"
            " media_type=excluded.media_type, original_filename=excluded.original_filename,"
            " imported_at=excluded.imported_at",
            (
                source.sha256,
                source.size_bytes,
                source.media_type,
                source.original_filename,
                source.imported_at,
            ),
        )

    def _write_source_minimal(self, sha256: str) -> None:
        self._conn.execute(
            "INSERT OR IGNORE INTO sources(sha256, size_bytes, media_type,"
            " original_filename, imported_at) VALUES(?,0,'unknown','unknown','')",
            (sha256,),
        )

    def upsert_document(self, revision: DocumentRevision) -> None:
        with self.transaction():
            self._insert_document(revision)

    def _insert_document(self, revision: DocumentRevision) -> None:
        self._write_source_minimal(revision.object_sha256)
        self._remove_document(revision.record_path)
        cur = self._conn.execute(
            "INSERT INTO documents(manufacturer, part_number, document_type,"
            " revision, object_sha256, record_path, title, date, page_count, summary)"
            " VALUES(?,?,?,?,?,?,?,?,?,?)",
            (
                revision.manufacturer,
                revision.part_number,
                revision.document_type,
                revision.revision,
                revision.object_sha256,
                revision.record_path,
                revision.title,
                revision.date,
                revision.page_count,
                revision.summary,
            ),
        )
        doc_id = int(cur.lastrowid)
        for alias in revision.aliases:
            self._conn.execute(
                "INSERT INTO aliases(owner_table, owner_id, value, kind)"
                " VALUES('documents',?,?,?)",
                (doc_id, alias.value, alias.kind),
            )
        for tag in revision.tags:
            self._conn.execute(
                "INSERT INTO tags(owner_table, owner_id, tag) VALUES('documents',?,?)",
                (doc_id, tag),
            )
        for field in revision.fields:
            self._index_field("documents", doc_id, field)
        content = " ".join(
            piece
            for piece in (
                revision.manufacturer,
                revision.part_number,
                revision.title,
                revision.summary,
                " ".join(alias.value for alias in revision.aliases),
                " ".join(revision.tags),
            )
            if piece
        )
        self._conn.execute(
            "INSERT INTO fts_docs(rowid, content) VALUES(?,?)", (doc_id, content)
        )

    def _index_field(self, owner_table: str, owner_id: int, field: object) -> None:
        value_num = (
            field.value
            if isinstance(field.value, (int, float)) and not isinstance(field.value, bool)
            else None
        )
        value_text = field.value if isinstance(field.value, str) else None
        page = field.provenance.page if field.provenance else None
        source_hash = field.provenance.source_hash if field.provenance else ""
        cur = self._conn.execute(
            "INSERT INTO fields(owner_table, owner_id, name, unit, value_text,"
            " value_num, value_min, value_typ, value_max, review_state, source_hash, page, conditions)"
            " VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (
                owner_table,
                owner_id,
                field.name,
                field.unit,
                value_text,
                value_num,
                field.value_min,
                field.value_typ,
                field.value_max,
                field.review_state,
                source_hash,
                page,
                field.conditions,
            ),
        )
        field_id = int(cur.lastrowid)
        self._conn.execute(
            "INSERT INTO fts_fields(rowid, content) VALUES(?,?)",
            (
                field_id,
                _field_search_text(field.name, field.unit, value_text, value_num, field.conditions),
            ),
        )

    def upsert_component(self, profile: ComponentProfile) -> None:
        with self.transaction():
            self._insert_component(profile)

    def _insert_component(self, profile: ComponentProfile) -> None:
        self._remove_component(
            profile.manufacturer, profile.part_number, profile.profile_version
        )
        if profile.source_object_sha256:
            self._write_source_minimal(profile.source_object_sha256)
        cur = self._conn.execute(
            "INSERT INTO components(manufacturer, part_number, profile_version,"
            " source_object_sha256, device_type, package) VALUES(?,?,?,?,?,?)",
            (
                profile.manufacturer,
                profile.part_number,
                profile.profile_version,
                profile.source_object_sha256,
                profile.device_type,
                profile.package,
            ),
        )
        comp_id = int(cur.lastrowid)
        for alias in profile.aliases:
            self._conn.execute(
                "INSERT INTO aliases(owner_table, owner_id, value, kind)"
                " VALUES('components',?,?,?)",
                (comp_id, alias.value, alias.kind),
            )
        for field in profile.fields:
            self._index_field("components", comp_id, field)
        content = " ".join(
            piece
            for piece in (
                profile.manufacturer,
                profile.part_number,
                profile.device_type,
                profile.package,
                " ".join(alias.value for alias in profile.aliases),
            )
            if piece
        )
        self._conn.execute(
            "INSERT INTO fts_components(rowid, content) VALUES(?,?)",
            (comp_id, content),
        )

    def upsert_magnetics(self, record: MagneticsRecord) -> None:
        with self.transaction():
            self._insert_magnetics(record)

    def _insert_magnetics(self, record: MagneticsRecord) -> None:
        self._remove_magnetics(
            record.manufacturer, record.family, record.kind, record.designation
        )
        cur = self._conn.execute(
            "INSERT INTO magnetics(manufacturer, family, kind, designation)"
            " VALUES(?,?,?,?)",
            (record.manufacturer, record.family, record.kind, record.designation),
        )
        mag_id = int(cur.lastrowid)
        for alias in record.aliases:
            self._conn.execute(
                "INSERT INTO aliases(owner_table, owner_id, value, kind)"
                " VALUES('magnetics',?,?,?)",
                (mag_id, alias.value, alias.kind),
            )
        for field in record.fields:
            self._index_field("magnetics", mag_id, field)
        content = " ".join(
            piece
            for piece in (
                record.manufacturer,
                record.family,
                record.designation,
                " ".join(alias.value for alias in record.aliases),
            )
            if piece
        )
        self._conn.execute(
            "INSERT INTO fts_magnetics(rowid, content) VALUES(?,?)",
            (mag_id, content),
        )

    def add_page_text(self, source_hash: str, page: int, text: str) -> None:
        with self.transaction():
            self._add_page_text(source_hash, page, text)

    def _add_page_text(self, source_hash: str, page: int, text: str) -> None:
        self._conn.execute(
            "INSERT INTO page_texts(source_hash, page, text) VALUES(?,?,?)"
            " ON CONFLICT(source_hash, page) DO UPDATE SET text=excluded.text",
            (source_hash, page, text),
        )
        rowid = self._conn.execute(
            "SELECT rowid_alias FROM page_texts WHERE source_hash=? AND page=?",
            (source_hash, page),
        ).fetchone()[0]
        self._conn.execute("DELETE FROM fts_pages WHERE rowid=?", (rowid,))
        self._conn.execute(
            "INSERT INTO fts_pages(rowid, content) VALUES(?,?)", (rowid, text)
        )

    def remove_document(self, record_path: str) -> None:
        with self.transaction():
            self._remove_document(record_path)

    def _remove_document(self, record_path: str) -> None:
        row = self._conn.execute(
            "SELECT id FROM documents WHERE record_path=?", (record_path,)
        ).fetchone()
        if not row:
            return
        self._delete_owner_rows("documents", int(row[0]))
        self._conn.execute("DELETE FROM documents WHERE id=?", (row[0],))

    def _remove_component(self, manufacturer: str, part_number: str, version: str) -> None:
        row = self._conn.execute(
            "SELECT id FROM components WHERE manufacturer=? AND part_number=? AND profile_version=?",
            (manufacturer, part_number, version),
        ).fetchone()
        if not row:
            return
        self._delete_owner_rows("components", int(row[0]))
        self._conn.execute("DELETE FROM components WHERE id=?", (row[0],))

    def _remove_magnetics(self, manufacturer: str, family: str, kind: str, designation: str) -> None:
        row = self._conn.execute(
            "SELECT id FROM magnetics WHERE manufacturer=? AND family=? AND kind=? AND designation=?",
            (manufacturer, family, kind, designation),
        ).fetchone()
        if not row:
            return
        self._delete_owner_rows("magnetics", int(row[0]))
        self._conn.execute("DELETE FROM magnetics WHERE id=?", (row[0],))

    def _delete_owner_rows(self, owner_table: str, owner_id: int) -> None:
        rows = self._conn.execute(
            "SELECT id FROM fields WHERE owner_table=? AND owner_id=?",
            (owner_table, owner_id),
        ).fetchall()
        for (field_id,) in rows:
            self._conn.execute("DELETE FROM fts_fields WHERE rowid=?", (field_id,))
        self._conn.execute(
            "DELETE FROM fields WHERE owner_table=? AND owner_id=?",
            (owner_table, owner_id),
        )
        self._conn.execute(
            "DELETE FROM aliases WHERE owner_table=? AND owner_id=?",
            (owner_table, owner_id),
        )
        self._conn.execute(
            "DELETE FROM tags WHERE owner_table=? AND owner_id=?",
            (owner_table, owner_id),
        )
        self._conn.execute(
            f"DELETE FROM {_OWNER_FTS[owner_table]} WHERE rowid=?", (owner_id,)
        )

    # -- rebuild ---------------------------------------------------------------

    def rebuild(
        self,
        records: Iterable[object] = (),
        page_texts: Iterable[tuple[str, int, str]] = (),
    ) -> IndexStats:
        """Atomically replace the index with one built from ``records``."""

        self._conn.close()
        new_index = self._build_atomic(self._path, records, page_texts)
        self.__dict__.update(new_index.__dict__)
        return self.stats()

    @classmethod
    def _build_atomic(
        cls,
        path: Path,
        records: Iterable[object],
        page_texts: Iterable[tuple[str, int, str]],
    ) -> "KnowledgeIndex":
        tmp_path = Path(str(path) + ".rebuild-tmp")
        for suffix in ("", "-wal", "-shm"):
            candidate = Path(str(tmp_path) + suffix)
            if candidate.exists():
                candidate.unlink()
        index = cls(tmp_path)
        try:
            with index.transaction():
                for record in records:
                    if isinstance(record, SourceObject):
                        index._write_source(record)
                    elif isinstance(record, DocumentRevision):
                        index._insert_document(record)
                    elif isinstance(record, ComponentProfile):
                        index._insert_component(record)
                    elif isinstance(record, MagneticsRecord):
                        index._insert_magnetics(record)
                for source_hash, page, text in page_texts:
                    index._add_page_text(source_hash, page, text)
        except BaseException:
            index.close()
            for suffix in ("", "-wal", "-shm"):
                candidate = Path(str(tmp_path) + suffix)
                if candidate.exists():
                    candidate.unlink()
            raise
        index.close()
        os.replace(tmp_path, path)
        return cls(path)

    # -- reads ------------------------------------------------------------------

    def stats(self) -> IndexStats:
        def count(table: str) -> int:
            return int(self._conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0])

        return IndexStats(
            documents=count("documents"),
            components=count("components"),
            magnetics=count("magnetics"),
            fields=count("fields"),
            pages=count("page_texts"),
            sources=count("sources"),
        )

    def check_integrity(self) -> bool:
        try:
            row = self._conn.execute("PRAGMA integrity_check").fetchone()
            return bool(row) and row[0] == "ok"
        except sqlite3.DatabaseError:
            return False

    def search(
        self,
        query: str,
        *,
        kinds: Sequence[str] | None = None,
        limit: int = 50,
    ) -> list[SearchHit]:
        """Search records and page text; grouped by kind, rank-ordered."""

        filters, terms = parse_query(query)
        match = _fts_match(terms)
        wanted = tuple(kinds) if kinds else _KIND_ORDER
        per_kind_limit = max(1, limit)
        hits: list[SearchHit] = []
        if "document" in wanted:
            hits.extend(self._search_documents(match, filters, per_kind_limit))
        if "component" in wanted:
            hits.extend(self._search_components(match, filters, per_kind_limit))
        if "magnetics" in wanted:
            hits.extend(self._search_magnetics(match, filters, per_kind_limit))
        if "field" in wanted:
            hits.extend(self._search_fields(match, filters, per_kind_limit))
        if "page" in wanted:
            hits.extend(self._search_pages(match, per_kind_limit))
        return hits[:limit] if limit else hits

    @staticmethod
    def _where(clauses: list[str]) -> str:
        return (" WHERE " + " AND ".join(clauses)) if clauses else ""

    def _search_documents(self, match: str | None, filters: dict[str, str], limit: int) -> list[SearchHit]:
        clauses: list[str] = []
        params: list[object] = []
        if match:
            clauses.append("fts_docs.content MATCH ?")
            params.append(match)
        if "maker" in filters:
            clauses.append("d.manufacturer LIKE ?")
            params.append(f"%{filters['maker']}%")
        if "type" in filters:
            clauses.append("d.document_type = ?")
            params.append(filters["type"])
        order = "ORDER BY bm25(fts_docs), d.id" if match else "ORDER BY d.id"
        sql = (
            "SELECT d.id, d.manufacturer, d.part_number, d.revision, d.title,"
            " d.object_sha256,"
            " snippet(fts_docs, 0, '«', '»', ' …', 12), bm25(fts_docs)"
            " FROM fts_docs JOIN documents d ON d.id = fts_docs.rowid"
            + self._where(clauses)
            + f" {order} LIMIT ?"
        )
        try:
            rows = self._conn.execute(sql, (*params, limit)).fetchall()
        except sqlite3.OperationalError:
            return []
        return [
            SearchHit(
                kind="document",
                title=title or f"{maker} {part}",
                subtitle=f"{maker} · {part} · سند {revision}",
                snippet=snippet or "",
                ref={
                    "record_kind": "document-revision",
                    "id": doc_id,
                    "source_hash": source_hash,
                },
                rank=float(rank),
            )
            for doc_id, maker, part, revision, title, source_hash, snippet, rank in rows
        ]

    def _search_components(self, match: str | None, filters: dict[str, str], limit: int) -> list[SearchHit]:
        clauses: list[str] = []
        params: list[object] = []
        if match:
            clauses.append("fts_components.content MATCH ?")
            params.append(match)
        if "maker" in filters:
            clauses.append("c.manufacturer LIKE ?")
            params.append(f"%{filters['maker']}%")
        order = "ORDER BY bm25(fts_components), c.id" if match else "ORDER BY c.manufacturer, c.part_number, c.id"
        sql = (
            "SELECT c.id, c.manufacturer, c.part_number, c.profile_version,"
            " c.source_object_sha256,"
            " snippet(fts_components, 0, '«', '»', ' …', 12), bm25(fts_components)"
            " FROM fts_components JOIN components c ON c.id = fts_components.rowid"
            + self._where(clauses)
            + f" {order} LIMIT ?"
        )
        try:
            rows = self._conn.execute(sql, (*params, limit)).fetchall()
        except sqlite3.OperationalError:
            return []
        return [
            SearchHit(
                kind="component",
                title=f"{maker} {part}",
                subtitle=f"پروفایل {version}",
                snippet=snippet or "",
                ref={
                    "record_kind": "component-profile",
                    "id": cid,
                    "source_hash": source_hash,
                },
                rank=float(rank),
            )
            for cid, maker, part, version, source_hash, snippet, rank in rows
        ]

    def _search_magnetics(self, match: str | None, filters: dict[str, str], limit: int) -> list[SearchHit]:
        clauses: list[str] = []
        params: list[object] = []
        if match:
            clauses.append("fts_magnetics.content MATCH ?")
            params.append(match)
        if "core" in filters:
            clauses.append("(m.family LIKE ? OR m.designation LIKE ?)")
            params.extend((f"%{filters['core']}%", f"%{filters['core']}%"))
        order = "ORDER BY bm25(fts_magnetics), m.id" if match else "ORDER BY m.id"
        sql = (
            "SELECT m.id, m.manufacturer, m.family, m.kind, m.designation,"
            " snippet(fts_magnetics, 0, '«', '»', ' …', 12), bm25(fts_magnetics)"
            " FROM fts_magnetics JOIN magnetics m ON m.id = fts_magnetics.rowid"
            + self._where(clauses)
            + f" {order} LIMIT ?"
        )
        try:
            rows = self._conn.execute(sql, (*params, limit)).fetchall()
        except sqlite3.OperationalError:
            return []
        return [
            SearchHit(
                kind="magnetics",
                title=f"{family} · {designation}",
                subtitle=f"{maker} · {kind}",
                snippet=snippet or "",
                ref={"record_kind": "magnetics-record", "id": mid},
                rank=float(rank),
            )
            for mid, maker, family, kind, designation, snippet, rank in rows
        ]

    def _search_fields(self, match: str | None, filters: dict[str, str], limit: int) -> list[SearchHit]:
        clauses: list[str] = []
        params: list[object] = []
        if match:
            clauses.append("fts_fields.content MATCH ?")
            params.append(match)
        if "material" in filters:
            clauses.append(
                "(fl.name LIKE 'material%' AND"
                " (fl.value_text LIKE ? OR CAST(fl.value_num AS TEXT) LIKE ?))"
            )
            params.extend((f"%{filters['material']}%", f"%{filters['material']}%"))
        if "verified" in filters:
            if filters["verified"].casefold() in ("yes", "true", "1"):
                clauses.append("fl.review_state = 'verified'")
            else:
                clauses.append("fl.review_state != 'verified'")
        order = "ORDER BY bm25(fts_fields), fl.id" if match else "ORDER BY fl.id"
        sql = (
            "SELECT fl.id, fl.owner_table, fl.owner_id, fl.name, fl.unit, fl.value_num,"
            " fl.value_text, fl.review_state, fl.source_hash, fl.page,"
            " snippet(fts_fields, 0, '«', '»', ' …', 10), bm25(fts_fields)"
            " FROM fts_fields JOIN fields fl ON fl.id = fts_fields.rowid"
            + self._where(clauses)
            + f" {order} LIMIT ?"
        )
        try:
            rows = self._conn.execute(sql, (*params, limit)).fetchall()
        except sqlite3.OperationalError:
            return []
        hits = []
        for row in rows:
            (
                fid, owner_table, owner_id, name, unit, value_num,
                value_text, review_state, source_hash, page, snippet, rank,
            ) = row
            owner_title, owner_sub = _field_owner_title(self._conn, owner_table, owner_id)
            value_repr = (
                value_text
                if value_text is not None
                else (f"{value_num:g}" if value_num is not None else "—")
            )
            hits.append(
                SearchHit(
                    kind="field",
                    title=f"{name} = {value_repr}" + (f" {unit}" if unit else ""),
                    subtitle=f"{owner_title} · {owner_sub} · وضعیت: {review_state}",
                    snippet=snippet or "",
                    ref={
                        "record_kind": "field",
                        "field_id": fid,
                        "owner_table": owner_table,
                        "owner_id": owner_id,
                        "source_hash": source_hash,
                        "page": page,
                    },
                    rank=float(rank),
                )
            )
        return hits

    def _search_pages(self, match: str | None, limit: int) -> list[SearchHit]:
        if not match:
            return []
        sql = (
            "SELECT p.source_hash, p.page, snippet(fts_pages, 0, '«', '»', ' …', 12), bm25(fts_pages)"
            " FROM fts_pages JOIN page_texts p ON p.rowid_alias = fts_pages.rowid"
            " WHERE fts_pages.content MATCH ?"
            " ORDER BY bm25(fts_pages), p.source_hash, p.page LIMIT ?"
        )
        try:
            rows = self._conn.execute(sql, (match, limit)).fetchall()
        except sqlite3.OperationalError:
            return []
        return [
            SearchHit(
                kind="page",
                title=f"صفحه {page}",
                subtitle=f"منبع {source_hash[:12]}…",
                snippet=snippet or "",
                ref={"record_kind": "page", "source_hash": source_hash, "page": page},
                rank=float(rank),
            )
            for source_hash, page, snippet, rank in rows
        ]
