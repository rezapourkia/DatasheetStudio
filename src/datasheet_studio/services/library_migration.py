"""Application service for the safe v1 → v2 library migration (Phase 4).

Orchestrates ``KnowledgeVault`` over a v1 ``LibraryStore`` following
``docs/modules/LIBRARY_UPGRADE.md``: preview, per-item import with duplicate
detection, skipped/failed/ambiguous reporting, index rebuild, report files,
cancellation, and rollback.  The v1 library is never modified.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Callable

from datasheet_studio.infrastructure.pdf.reader import is_valid_pdf_file
from datasheet_studio.infrastructure.storage.knowledge_vault import (
    KnowledgeVault,
    VaultError,
)
from datasheet_studio.infrastructure.storage.library_store import LibraryStore
from datasheet_studio.models.knowledge_base import DocumentRevision
from datasheet_studio.models.library_item import LibraryItemKind

ENTRY_KINDS = ("imported", "duplicate", "skipped", "failed", "ambiguous")

_KIND_TO_DOC_TYPE = {
    LibraryItemKind.DATASHEET: "datasheet",
    LibraryItemKind.APPLICATION_NOTE: "application-note",
    LibraryItemKind.SOFTWARE: "other",
}


class MigrationError(RuntimeError):
    """The migration could not complete and was rolled back."""


class MigrationCancelled(MigrationError):
    """The user cancelled the migration; the partial vault was removed."""


@dataclass(frozen=True)
class MigrationEntry:
    kind: str  # imported | duplicate | skipped | failed | ambiguous
    title: str
    path: str
    reason: str = ""
    sha256: str = ""


@dataclass
class MigrationPreview:
    source_root: str
    item_count: int = 0
    files_found: int = 0
    files_missing: int = 0
    total_bytes: int = 0


@dataclass
class MigrationReport:
    source_root: str
    target_root: str
    started_at: str = ""
    finished_at: str = ""
    entries: list[MigrationEntry] = field(default_factory=list)

    def count(self, kind: str) -> int:
        return sum(1 for entry in self.entries if entry.kind == kind)

    def to_json(self) -> str:
        return json.dumps(
            {
                "source_root": self.source_root,
                "target_root": self.target_root,
                "started_at": self.started_at,
                "finished_at": self.finished_at,
                "entries": [entry.__dict__ for entry in self.entries],
            },
            ensure_ascii=False,
            indent=2,
        ) + "\n"

    def to_markdown(self) -> str:
        lines = [
            "# گزارش ارتقای کتابخانه به نسخهٔ ۲",
            "",
            f"- کتابخانه مبدأ: `{self.source_root}`",
            f"- ولت مقصد: `{self.target_root}`",
            f"- شروع: {self.started_at} — پایان: {self.finished_at or '—'}",
            "",
            "| نتیجه | تعداد |",
            "|---|---:|",
        ]
        for kind in ENTRY_KINDS:
            lines.append(f"| {kind} | {self.count(kind)} |")
        lines.append("")
        for kind in ENTRY_KINDS:
            subset = [e for e in self.entries if e.kind == kind]
            if not subset:
                continue
            lines.append(f"## {kind} ({len(subset)})")
            lines.append("")
            for entry in subset:
                lines.append(f"- **{entry.title}** — {entry.path}")
                if entry.reason:
                    lines.append(f"  - دلیل: {entry.reason}")
            lines.append("")
        lines.append(
            "> فایل‌های v1 دست‌نخورده‌اند؛ حذف یا بازنویسی‌ای روی مبدأ انجام نشده است."
        )
        return "\n".join(lines) + "\n"


ProgressCallback = Callable[[int, int, str], None]
CancelCheck = Callable[[], bool]


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


class LibraryMigrator:
    """Runs the v1 → v2 migration with full safety rules."""

    def preview(self, source_root: str | Path) -> MigrationPreview:
        store = LibraryStore(source_root)
        preview = MigrationPreview(source_root=str(store.root))
        preview.item_count = store.item_count
        for item in store.items:
            path = store.item_path(item)
            if path.is_file():
                preview.files_found += 1
                preview.total_bytes += path.stat().st_size
            else:
                preview.files_missing += 1
        return preview

    def migrate(
        self,
        source_root: str | Path,
        target_root: str | Path,
        progress: ProgressCallback | None = None,
        should_cancel: CancelCheck | None = None,
    ) -> MigrationReport:
        store = LibraryStore(source_root)
        report = MigrationReport(
            source_root=str(store.root),
            target_root=str(Path(target_root)),
            started_at=_now(),
        )
        try:
            vault = KnowledgeVault.create(target_root, name=store.name)
        except VaultError as exc:
            raise MigrationError(str(exc)) from exc

        records: list[DocumentRevision] = []
        seen_hashes: set[str] = set()
        total = store.item_count

        try:
            vault.backup_manifest(store.root / "library.json")
            for position, item in enumerate(store.items, start=1):
                if should_cancel and should_cancel():
                    raise MigrationCancelled("مهاجرت توسط کاربر لغو شد.")
                label = item.title or item.part_number or item.relative_path
                if progress:
                    progress(position, total, label)

                source_path = store.item_path(item)
                if not source_path.is_file():
                    report.entries.append(
                        MigrationEntry("skipped", label, item.relative_path, "فایل یافت نشد")
                    )
                    continue
                if not is_valid_pdf_file(source_path):
                    report.entries.append(
                        MigrationEntry(
                            "skipped", label, item.relative_path, "فایل PDF معتبر نیست"
                        )
                    )
                    continue

                try:
                    digest, _size, copied = vault.import_source(source_path)
                except VaultError as exc:
                    report.entries.append(
                        MigrationEntry("failed", label, item.relative_path, str(exc))
                    )
                    continue

                if digest in seen_hashes:
                    report.entries.append(
                        MigrationEntry(
                            "duplicate",
                            label,
                            item.relative_path,
                            "محتوای تکراری؛ شیء منبع قبلاً وارد شده است",
                            digest,
                        )
                    )
                else:
                    seen_hashes.add(digest)
                    report.entries.append(
                        MigrationEntry("imported", label, item.relative_path, "", digest)
                    )

                manufacturer = (item.manufacturer or item.manufacturer_folder or "").strip()
                part_number = (item.part_number or "").strip()
                ambiguous_reasons = []
                if not manufacturer:
                    manufacturer = "unknown"
                    ambiguous_reasons.append("سازنده نامشخص")
                if not part_number:
                    part_number = Path(item.relative_path).stem
                    ambiguous_reasons.append("شماره قطعه از نام فایل گرفته شد")
                if ambiguous_reasons:
                    report.entries.append(
                        MigrationEntry(
                            "ambiguous",
                            label,
                            item.relative_path,
                            "؛ ".join(ambiguous_reasons),
                            digest,
                        )
                    )

                record_dir = vault.unique_record_dir(
                    manufacturer, part_number, "migrated-1"
                )
                revision = DocumentRevision(
                    manufacturer=manufacturer,
                    part_number=part_number,
                    document_type=_KIND_TO_DOC_TYPE.get(item.kind, "other"),
                    revision="migrated-1",
                    object_sha256=digest,
                    record_path=record_dir.relative_to(vault.root).as_posix()
                    + "/record.md",
                    title=item.title or part_number,
                    date=item.added_at[:10] if item.added_at else "",
                    page_count=item.page_count or None,
                    tags=tuple(item.tags),
                    summary="",
                )
                markdown = _record_markdown(revision, item.summary_text)
                vault.write_document_record(record_dir, revision, markdown)
                records.append(revision)

            vault.rebuild_index(records)
            report.finished_at = _now()
            vault.write_migration_report(report.to_json(), report.to_markdown())
        except MigrationCancelled:
            vault.rollback()
            raise
        except BaseException as exc:  # noqa: BLE001 - abort + cleanup semantics
            vault.rollback()
            raise MigrationError(f"مهاجرت ناتمام ماند و ولت حذف شد: {exc}") from exc
        return report

    def rollback(self, target_root: str | Path) -> None:
        KnowledgeVault(target_root).rollback()


def _record_markdown(revision: DocumentRevision, summary_text: str) -> str:
    lines = [
        f"# {revision.title or revision.part_number}",
        "",
        f"- سازنده: {revision.manufacturer}",
        f"- شماره قطعه: {revision.part_number}",
        f"- نوع سند: {revision.document_type}",
        f"- تاریخ افزودن (v1): {revision.date or '—'}",
        f"- صفحات: {revision.page_count or '—'}",
        f"- برچسب‌ها: {', '.join(revision.tags) if revision.tags else '—'}",
        f"- شیء منبع: `objects/sha256/{revision.object_sha256[:2]}/{revision.object_sha256}.pdf`",
        "- منبع رکورد: مهاجرت از کتابخانه v1 (`library.json`)",
        "",
        "## خلاصه",
        "",
        summary_text.strip() or "—",
        "",
        "> این رکورد از داده‌های v1 درون‌ریزی شده و تأییدنشده است.",
    ]
    return "\n".join(lines) + "\n"
