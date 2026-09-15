"""Validated online download + preview-before-save into the v2 vault.

Implements the Phase 6 download-safety contract: explicit user action only,
content-type/%PDF/size/hash checks, temporary preview, and save into the
accepted knowledge vault with duplicate resolution — never marking anything
verified.  See ``docs/modules/ONLINE_ADAPTER_FRAMEWORK.md`` §5.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from pathlib import Path
import tempfile
from typing import Callable
from uuid import uuid4

from datasheet_studio.infrastructure.storage.knowledge_index import KnowledgeIndex
from datasheet_studio.infrastructure.storage.knowledge_vault import KnowledgeVault
from datasheet_studio.infrastructure.web.http_client import (
    DownloadedFile,
    HttpClient,
)
from datasheet_studio.models.knowledge_base import DocumentRevision

PREVIEW_DIR = Path(tempfile.gettempdir()) / "datasheet-studio-preview"


class OnlineImportError(RuntimeError):
    """A download or vault import could not complete."""


@dataclass(frozen=True)
class SaveOutcome:
    """What happened when an online PDF was saved."""

    record_path: str
    sha256: str
    duplicate: bool


class OnlineImportService:
    """Download online PDFs safely and save them into the knowledge vault."""

    def __init__(
        self,
        vault_path_getter: Callable[[], str],
        http: HttpClient | None = None,
    ) -> None:
        self._vault_path_getter = vault_path_getter
        self._http = http or HttpClient()

    def download_pdf(
        self,
        url: str,
        *,
        cancel_check: Callable[[], bool] | None = None,
    ) -> DownloadedFile:
        """Download to a temp file with validation; nothing is stored yet."""

        if not url or not url.strip():
            raise OnlineImportError("نشانی فایل PDF موجود نیست.")
        PREVIEW_DIR.mkdir(parents=True, exist_ok=True)
        destination = PREVIEW_DIR / f"{uuid4().hex}.pdf"
        try:
            return self._http.download_file(
                url.strip(),
                destination,
                expect_pdf=True,
                cancel_check=cancel_check,
            )
        except OnlineImportError:
            raise
        except Exception as exc:  # noqa: BLE001 - single clear error type for UI
            raise OnlineImportError(str(exc)) from exc

    def save_to_vault(
        self,
        downloaded: DownloadedFile,
        *,
        manufacturer: str,
        part_number: str,
        title: str = "",
    ) -> SaveOutcome:
        """Import a validated download into the accepted v2 vault."""

        vault = self._accepted_vault()
        try:
            digest, _size, copied = vault.import_source(downloaded.path)
        except Exception as exc:  # noqa: BLE001
            raise OnlineImportError(str(exc)) from exc

        revision_label = f"online-{date.today():%Y%m%d}"
        maker = (manufacturer or "").strip() or "unknown"
        part = (part_number or "").strip() or Path(downloaded.path).stem
        record_dir = vault.unique_record_dir(maker, part, revision_label)
        revision = DocumentRevision(
            manufacturer=maker,
            part_number=part,
            document_type="datasheet",
            revision=revision_label,
            object_sha256=digest,
            record_path=record_dir.relative_to(vault.root).as_posix() + "/record.md",
            title=(title or "").strip() or part,
            summary="درون‌ریزی از منبع آنلاین؛ تأییدنشده.",
        )
        markdown = _record_markdown(revision, downloaded.final_url)
        try:
            vault.write_document_record(record_dir, revision, markdown)
        except Exception as exc:  # noqa: BLE001
            raise OnlineImportError(str(exc)) from exc

        index = KnowledgeIndex.open(vault.index_path)
        try:
            index.upsert_document(revision)
        except Exception as exc:  # noqa: BLE001
            raise OnlineImportError(f"بروزرسانی ایندکس ناموفق بود: {exc}") from exc
        finally:
            index.close()

        return SaveOutcome(
            record_path=revision.record_path,
            sha256=digest,
            duplicate=not copied,
        )

    def _accepted_vault(self) -> KnowledgeVault:
        raw = (self._vault_path_getter() or "").strip()
        if not raw:
            raise OnlineImportError(
                "ولت دانش v2 فعالی وجود ندارد؛ ابتدا از Library → Upgrade Library to v2 "
                "کتابخانه را ارتقا دهید و تأیید نهایی کنید."
            )
        vault = KnowledgeVault(raw)
        if not vault.exists():
            raise OnlineImportError(f"پوشه ولت پیدا نشد: {raw}")
        try:
            _identity, accepted = vault.read_identity()
        except Exception as exc:  # noqa: BLE001
            raise OnlineImportError(f"خواندن library.toml ممکن نشد: {exc}") from exc
        if not accepted:
            raise OnlineImportError(
                "ولت هنوز تأیید نهایی نشده است؛ ابتدا مهاجرت را Accept کنید."
            )
        return vault


def _record_markdown(revision: DocumentRevision, final_url: str) -> str:
    lines = [
        f"# {revision.title}",
        "",
        f"- سازنده: {revision.manufacturer}",
        f"- شماره قطعه: {revision.part_number}",
        f"- نوع سند: datasheet (دانلود آنلاین)",
        f"- تاریخ درون‌ریزی: {revision.revision.removeprefix('online-')}",
        f"- منبع: `{final_url or '—'}`",
        f"- شیء منبع: `objects/sha256/{revision.object_sha256[:2]}/{revision.object_sha256}.pdf`",
        "",
        "> این سند از منبع آنلاین ذخیره شده و از نظر مهندسی تأییدنشده است.",
    ]
    return "\n".join(lines) + "\n"
