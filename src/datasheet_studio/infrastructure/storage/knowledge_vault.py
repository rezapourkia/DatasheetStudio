"""On-disk writer for the v2 engineering knowledge-base vault.

Implements the layout in ``docs/modules/ENGINEERING_KNOWLEDGE_BASE.md`` §2
for the Phase 4 migration: content-addressed objects, human Markdown records
next to machine envelopes, a TOML identity file, and the rebuildable
SQLite index.  Everything here is stdlib + the Phase 2/3 modules; no Qt.
"""

from __future__ import annotations

from datetime import datetime, timezone
import os
from pathlib import Path
import shutil
import tomllib
import uuid

from datasheet_studio.infrastructure.storage.knowledge_index import KnowledgeIndex
from datasheet_studio.models.knowledge_base import (
    SCHEMA_VERSION,
    DocumentRevision,
    LibraryIdentity,
    dump_record,
)
from datasheet_studio.services.knowledge_hash import sha256_file

IDENTITY_FILENAME = "library.toml"
INDEX_FILENAME = "library.sqlite"
MIGRATION_DIR = "migration"


class VaultError(RuntimeError):
    """A vault operation failed."""


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _toml_escape(value: str) -> str:
    return value.replace("\\", "\\\\").replace('"', '\\"')


def _safe_segment(name: str) -> str:
    cleaned = "".join(
        ch if ch.isalnum() or ch in "-_ ." else "_" for ch in str(name)
    ).strip()
    return cleaned or "untitled"


class KnowledgeVault:
    """Read/write access to one v2 vault folder."""

    def __init__(self, root: str | Path) -> None:
        self._root = Path(root)

    @property
    def root(self) -> Path:
        return self._root

    @property
    def identity_path(self) -> Path:
        return self._root / IDENTITY_FILENAME

    @property
    def index_path(self) -> Path:
        return self._root / INDEX_FILENAME

    # -- creation and identity ------------------------------------------------

    @classmethod
    def create(cls, root: str | Path, name: str) -> "KnowledgeVault":
        """Create a fresh vault folder; refuses to touch an existing one."""

        vault = cls(root)
        if vault._root.exists() and any(vault._root.iterdir()):
            raise VaultError(
                f"پوشه مقصد خالی نیست: {vault._root}"
            )
        try:
            (vault._root / "objects" / "sha256").mkdir(parents=True, exist_ok=True)
            (vault._root / "records").mkdir(parents=True, exist_ok=True)
            (vault._root / MIGRATION_DIR).mkdir(parents=True, exist_ok=True)
        except OSError as exc:
            raise VaultError(f"ساخت پوشه‌های ولت ممکن نشد: {exc}") from exc
        vault.write_identity(name=name, accepted=False)
        return vault

    def write_identity(self, name: str, *, accepted: bool) -> LibraryIdentity:
        identity = LibraryIdentity(
            library_id=uuid.uuid4().hex,
            name=name,
            created_at=_now_iso(),
            last_modified_at=_now_iso(),
            schema_version=SCHEMA_VERSION,
        )
        lines = [
            f'schema_version = {SCHEMA_VERSION}',
            f'library_id = "{identity.library_id}"',
            f'name = "{_toml_escape(name)}"',
            f'created_at = "{identity.created_at}"',
            f'last_modified_at = "{identity.last_modified_at}"',
            f'accepted = {"true" if accepted else "false"}',
        ]
        try:
            self.identity_path.write_text(
                "\n".join(lines) + "\n", encoding="utf-8"
            )
        except OSError as exc:
            raise VaultError(f"نوشتن library.toml ممکن نشد: {exc}") from exc
        return identity

    def read_identity(self) -> tuple[LibraryIdentity, bool]:
        """Return the validated identity and the ``accepted`` flag."""

        try:
            data = tomllib.loads(self.identity_path.read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError, tomllib.TOMLDecodeError) as exc:
            raise VaultError(f"خواندن library.toml ممکن نشد: {exc}") from exc
        identity = LibraryIdentity(
            library_id=str(data["library_id"]),
            name=str(data["name"]),
            created_at=str(data["created_at"]),
            last_modified_at=str(data.get("last_modified_at", "")),
            schema_version=int(data.get("schema_version", 0)),
        )
        return identity, bool(data.get("accepted", False))

    def mark_accepted(self) -> None:
        _, accepted = self.read_identity()
        if accepted:
            return
        try:
            text = self.identity_path.read_text(encoding="utf-8")
        except OSError as exc:
            raise VaultError(f"خواندن library.toml ممکن نشد: {exc}") from exc
        text = text.replace("accepted = false", "accepted = true")
        self.identity_path.write_text(text, encoding="utf-8")

    # -- objects ---------------------------------------------------------------

    def import_source(self, path: str | Path) -> tuple[str, int, bool]:
        """Copy a file into ``objects/sha256`` deduplicated by content hash.

        Returns ``(sha256, size_bytes, copied)``; ``copied`` is False when
        the object already existed (duplicate resolution).
        """

        source = Path(path)
        digest = sha256_file(source)
        size = source.stat().st_size
        target = self._root / "objects" / "sha256" / digest[:2] / f"{digest}.pdf"
        if target.is_file() and target.stat().st_size == size:
            return digest, size, False
        target.parent.mkdir(parents=True, exist_ok=True)
        try:
            shutil.copy2(source, target)
        except OSError as exc:
            raise VaultError(f"کپی فایل منبع ممکن نشد ({source}): {exc}") from exc
        return digest, size, True

    def object_path(self, sha256: str) -> Path:
        return self._root / "objects" / "sha256" / sha256[:2] / f"{sha256}.pdf"

    # -- records -----------------------------------------------------------------

    def unique_record_dir(self, maker: str, part: str, revision: str) -> Path:
        """Reserve and create the next free record directory."""

        base = (
            self._root
            / "records"
            / "datasheets"
            / _safe_segment(maker)
            / _safe_segment(part)
            / _safe_segment(revision)
        )
        candidate = base
        index = 2
        while candidate.exists():
            candidate = base.with_name(f"{base.name}-{index}")
            index += 1
        candidate.mkdir(parents=True, exist_ok=False)
        return candidate

    def write_document_record(
        self, record_dir: Path, revision: DocumentRevision, markdown: str
    ) -> Path:
        """Write ``record.md`` + the machine envelope inside ``record_dir``."""

        record_md = record_dir / "record.md"
        record_json = record_dir / "record.json"
        try:
            record_md.write_text(markdown, encoding="utf-8")
            record_json.write_text(dump_record(revision), encoding="utf-8")
        except OSError as exc:
            raise VaultError(f"نوشتن رکورد ممکن نشد ({record_dir}): {exc}") from exc
        return record_md

    def write_controller_profile(self, profile, index: bool = True) -> Path:
        """Store a controller profile envelope under records/components."""

        from datasheet_studio.models.controller_profile import dump_controller_profile

        record_dir = (
            self._root
            / "records"
            / "components"
            / _safe_segment(profile.manufacturer)
            / _safe_segment(profile.part_number)
            / _safe_segment(profile.profile_version)
        )
        suffix = 2
        while record_dir.exists():
            record_dir = record_dir.with_name(f"{record_dir.name}-{suffix}")
            suffix += 1
        record_dir.mkdir(parents=True, exist_ok=False)
        target = record_dir / "profile.json"
        try:
            target.write_text(dump_controller_profile(profile), encoding="utf-8")
        except OSError as exc:
            raise VaultError(f"نوشتن پروفایل کنترلر ممکن نشد: {exc}") from exc
        if index:
            from datasheet_studio.models.knowledge_base import ComponentProfile

            index_record = ComponentProfile(
                manufacturer=profile.manufacturer,
                part_number=profile.part_number,
                profile_version=profile.profile_version,
                source_object_sha256=profile.source_object_sha256,
                device_type="switching-controller",
                package=profile.package,
                fields=profile.fields,
                contradictions=profile.contradictions,
                unknown_facts=profile.unknown_facts,
                notes=profile.notes,
            )
            knowledge_index = KnowledgeIndex.open(self.index_path)
            try:
                knowledge_index.upsert_component(index_record)
            finally:
                knowledge_index.close()
        return target

    def write_catalog_pack(self, pack) -> Path:
        """Store a validated catalogue pack at catalogs/<provider>/<version>/."""

        from datasheet_studio.models.magnetics_catalog import dump_pack

        folder = (
            self._root / "catalogs"
            / _safe_segment(pack.provider) / _safe_segment(pack.pack_version)
        )
        folder.mkdir(parents=True, exist_ok=True)
        target = folder / "pack.json"
        target.write_text(dump_pack(pack), encoding="utf-8")
        manifest = (
            f"# {pack.provider} — pack {pack.pack_version}\n\n"
            f"- cores: {len(pack.cores)}\n"
            f"- materials: {len(pack.materials)}\n"
            f"- bobbins: {len(pack.bobbins)}\n"
            f"- manifest hash: `{pack.manifest_hash or '—'}`\n"
        )
        (folder / "manifest.md").write_text(manifest, encoding="utf-8",
        )
        return target

    def catalog_packs(self) -> list:
        """All installed packs, newest-last per provider (offline cache)."""

        from datasheet_studio.models.magnetics_catalog import load_pack

        packs = []
        root = self._root / "catalogs"
        if not root.is_dir():
            return []
        for target in sorted(root.glob("*/*/pack.json")):
            try:
                packs.append(load_pack(target.read_text(encoding="utf-8")))
            except Exception:
                continue
        return packs

    def rollback_catalog_pack(self, provider: str, pack_version: str) -> None:
        """Delete one installed pack version (pack files only, never user data)."""

        import shutil as _shutil

        folder = (
            self._root / "catalogs"
            / _safe_segment(provider) / _safe_segment(pack_version)
        )
        if folder.exists():
            _shutil.rmtree(folder)

    def latest_catalog_pack(self, provider: str):
        packs = [p for p in self.catalog_packs() if p.provider == provider]
        return packs[-1] if packs else None

    def controller_profiles_for(self, source_hash: str) -> list:
        """Newest-first controller profiles in this vault bound to a source."""

        from datasheet_studio.models.controller_profile import (
            ControllerProfile,
            load_controller_profile,
        )

        profiles: list[ControllerProfile] = []
        for candidate in (self._root / "records" / "components").rglob("profile.json"):
            try:
                profile = load_controller_profile(
                    candidate.read_text(encoding="utf-8")
                )
            except Exception:  # noqa: BLE001 - skip unreadable records
                continue
            if profile.source_object_sha256 == source_hash:
                profiles.append(profile)
        profiles.sort(key=lambda item: item.profile_version, reverse=True)
        return profiles

    # -- migration artifacts -------------------------------------------------------

    def backup_manifest(self, manifest_path: str | Path) -> Path:
        target = self._root / MIGRATION_DIR / "backup-library.json"
        try:
            shutil.copy2(manifest_path, target)
        except OSError as exc:
            raise VaultError(f"نسخه پشتیبان منیفست ممکن نشد: {exc}") from exc
        return target

    def write_migration_report(self, report_json: str, report_markdown: str) -> Path:
        target = self._root / MIGRATION_DIR / "report.md"
        try:
            (self._root / MIGRATION_DIR / "report.json").write_text(
                report_json, encoding="utf-8"
            )
            target.write_text(report_markdown, encoding="utf-8")
        except OSError as exc:
            raise VaultError(f"نوشتن گزارش مهاجرت ممکن نشد: {exc}") from exc
        return target

    # -- index -----------------------------------------------------------------------

    def rebuild_index(
        self,
        records: list[DocumentRevision],
        page_texts: list[tuple[str, int, str]] | None = None,
    ) -> None:
        index = KnowledgeIndex.open(self.index_path)
        try:
            index.rebuild(records, page_texts or [])
        finally:
            index.close()

    # -- teardown ----------------------------------------------------------------------

    def exists(self) -> bool:
        return self._root.is_dir()

    def rollback(self) -> None:
        """Delete the whole vault folder (v2 only; v1 is never touched)."""

        if not self._root.exists():
            return
        try:
            shutil.rmtree(self._root)
        except OSError as exc:
            raise VaultError(f"حذف ولت v2 ممکن نشد: {exc}") from exc
