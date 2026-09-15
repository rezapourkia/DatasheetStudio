"""Provider-neutral search coordination for the bottom search strip.

Phase 5 deliberately ships only the local knowledge-base provider and a
deterministic mock provider.  Network providers belong to Phase 6 and can be
added through the same protocol without changing the widget.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Protocol, Sequence
from urllib.parse import quote

from datasheet_studio.infrastructure.storage.knowledge_index import KnowledgeIndex
from datasheet_studio.infrastructure.storage.knowledge_vault import KnowledgeVault


@dataclass(frozen=True)
class SearchResult:
    """One normalized result from any local or future online provider."""

    provider_id: str
    kind: str
    title: str
    subtitle: str = ""
    snippet: str = ""
    pdf_path: str | None = None
    page: int | None = None
    url: str | None = None
    can_preview: bool = False
    can_save: bool = False
    source_label: str = ""

    @property
    def copy_target(self) -> str:
        """Return the useful link/path exposed by the Copy action."""

        return self.url or self.pdf_path or ""


@dataclass(frozen=True)
class SearchResponse:
    """Combined results plus isolated provider notices and failures."""

    results: tuple[SearchResult, ...] = ()
    notices: tuple[tuple[str, str], ...] = ()
    errors: tuple[tuple[str, str], ...] = ()


class SearchProviderUnavailable(RuntimeError):
    """A configured provider cannot currently be used (not a fatal search)."""


class SearchProvider(Protocol):
    """Small provider contract used by :class:`SearchService`."""

    provider_id: str

    def search(self, query: str, *, limit: int = 30) -> Sequence[SearchResult]: ...


class SearchService:
    """Fan a query out while ensuring one provider cannot hide another."""

    def __init__(self, providers: Sequence[SearchProvider]) -> None:
        self._providers = {provider.provider_id: provider for provider in providers}

    def search(
        self,
        query: str,
        *,
        provider_ids: Sequence[str] | None = None,
        limit: int = 30,
    ) -> SearchResponse:
        query = query.strip()
        if not query:
            return SearchResponse()

        wanted = tuple(provider_ids) if provider_ids else tuple(self._providers)
        results: list[SearchResult] = []
        notices: list[tuple[str, str]] = []
        errors: list[tuple[str, str]] = []
        for provider_id in wanted:
            provider = self._providers.get(provider_id)
            if provider is None:
                errors.append((provider_id, "ارائه‌دهندهٔ جست‌وجو شناخته‌شده نیست."))
                continue
            try:
                results.extend(provider.search(query, limit=limit))
            except SearchProviderUnavailable as exc:
                notices.append((provider_id, str(exc)))
            except Exception as exc:  # noqa: BLE001 - provider isolation is the contract
                errors.append((provider_id, str(exc)))
        return SearchResponse(
            results=tuple(results[:limit]),
            notices=tuple(notices),
            errors=tuple(errors),
        )


class LocalKnowledgeProvider:
    """Search one accepted v2 knowledge vault and resolve its PDF objects."""

    provider_id = "local-kb"
    source_label = "کتابخانهٔ محلی"

    def __init__(self, vault_path: str | Path | None) -> None:
        self._vault_path = Path(vault_path) if vault_path else None

    def search(self, query: str, *, limit: int = 30) -> Sequence[SearchResult]:
        if self._vault_path is None or not self._vault_path.is_dir():
            raise SearchProviderUnavailable(
                "کتابخانهٔ دانش v2 فعالی وجود ندارد؛ از مسیر Library → Upgrade Library to v2 آن را بسازید و تأیید کنید."
            )

        vault = KnowledgeVault(self._vault_path)
        try:
            _identity, accepted = vault.read_identity()
        except Exception as exc:  # noqa: BLE001 - convert vault parsing to provider state
            raise SearchProviderUnavailable(f"کتابخانهٔ دانش قابل خواندن نیست: {exc}") from exc
        if not accepted:
            raise SearchProviderUnavailable(
                "کتابخانهٔ دانش هنوز تأیید نهایی نشده است؛ مهاجرت را بازبینی و Accept کنید."
            )
        if not vault.index_path.is_file():
            raise SearchProviderUnavailable(
                "ایندکس کتابخانه پیدا نشد؛ بازسازی ایندکس در مرحلهٔ نگهداری کتابخانه لازم است."
            )

        with KnowledgeIndex.open(vault.index_path) as index:
            hits = index.search(query, limit=limit)

        normalized: list[SearchResult] = []
        for hit in hits:
            source_hash = str(hit.ref.get("source_hash") or "")
            object_path = vault.object_path(source_hash) if source_hash else None
            pdf_path = str(object_path.resolve()) if object_path and object_path.is_file() else None
            raw_page = hit.ref.get("page")
            page = int(raw_page) if isinstance(raw_page, int) and raw_page > 0 else None
            normalized.append(
                SearchResult(
                    provider_id=self.provider_id,
                    kind=hit.kind,
                    title=hit.title,
                    subtitle=hit.subtitle,
                    snippet=hit.snippet,
                    pdf_path=pdf_path,
                    page=page,
                    can_preview=pdf_path is not None,
                    can_save=False,
                    source_label=self.source_label,
                )
            )
        return normalized


class MockOnlineProvider:
    """Deterministic Phase-5 placeholder; it never performs network I/O."""

    provider_id = "mock-online"
    source_label = "نمایشی — بدون اینترنت"

    def search(self, query: str, *, limit: int = 30) -> Sequence[SearchResult]:
        clean = " ".join(query.split())
        slug = quote(clean, safe="")
        rows = (
            SearchResult(
                provider_id=self.provider_id,
                kind="datasheet",
                title=f"{clean} — نتیجهٔ نمایشی سازنده",
                subtitle="نمونهٔ رابط Phase 5؛ دادهٔ واقعی نیست",
                snippet="پیش‌نمایش و ذخیره پس از اتصال منبع رسمی در Phase 6 فعال می‌شود.",
                url=f"https://example.invalid/datasheets/{slug}",
                can_preview=False,
                can_save=False,
                source_label=self.source_label,
            ),
            SearchResult(
                provider_id=self.provider_id,
                kind="datasheet",
                title=f"{clean} — نتیجهٔ نمایشی دوم",
                subtitle="Mock deterministic result",
                snippet="این ردیف فقط برای تأیید چیدمان، وضعیت‌ها و اکشن Copy Link است.",
                url=f"https://example.invalid/components/{slug}",
                can_preview=False,
                can_save=False,
                source_label=self.source_label,
            ),
        )
        return rows[: max(0, limit)]


def create_phase5_search_service(vault_path: str | Path | None) -> SearchService:
    """Build the complete Phase-5 provider set without any network adapter."""

    return SearchService((LocalKnowledgeProvider(vault_path), MockOnlineProvider()))
