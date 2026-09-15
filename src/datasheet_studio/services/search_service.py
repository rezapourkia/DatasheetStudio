"""Provider-neutral, concurrent, cancellation-safe search coordination.

Phase 6 turns the Phase 5 sequential fan-out into a bounded thread pool that
runs inside the strip's worker thread, keeps per-provider failures isolated,
preserves provider order, and honours a cancellation event.  Domain result
types live in ``models/search.py`` so infrastructure adapters can share them.
"""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, wait
from pathlib import Path
import threading
from typing import Sequence

from datasheet_studio.infrastructure.storage.knowledge_index import KnowledgeIndex
from datasheet_studio.infrastructure.storage.knowledge_vault import KnowledgeVault
from datasheet_studio.infrastructure.web.digikey import DigiKeyCredentials, DigiKeyProvider
from datasheet_studio.models.search import (
    ProviderUnavailable,
    SearchProvider,
    SearchResponse,
    SearchResult,
)

__all__ = [
    "ProviderUnavailable",
    "SearchProvider",
    "SearchResponse",
    "SearchResult",
    "SearchService",
    "LocalKnowledgeProvider",
    "MockOnlineProvider",
    "create_search_service",
    "create_phase5_search_service",
]


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
        cancel_event: threading.Event | None = None,
    ) -> SearchResponse:
        query = query.strip()
        if not query:
            return SearchResponse()

        wanted = tuple(provider_ids) if provider_ids else tuple(self._providers)
        if cancel_event is not None and cancel_event.is_set():
            return SearchResponse(notices=(("search", "جست‌وجو پیش از شروع لغو شد."),))

        with ThreadPoolExecutor(max_workers=max(1, len(wanted))) as pool:
            futures = {}
            for provider_id in wanted:
                provider = self._providers.get(provider_id)
                if provider is None:
                    continue  # surfaced below as a per-provider error
                futures[provider_id] = pool.submit(provider.search, query, limit=limit)
            wait(list(futures.values()))

        results: list[SearchResult] = []
        notices: list[tuple[str, str]] = []
        errors: list[tuple[str, str]] = []
        cancelled = cancel_event is not None and cancel_event.is_set()
        for provider_id in wanted:
            future = futures.get(provider_id)
            if future is None:
                errors.append((provider_id, "ارائه‌دهندهٔ جست‌وجو فعال نیست."))
                continue
            try:
                results.extend(future.result())
            except ProviderUnavailable as exc:
                notices.append((provider_id, str(exc)))
            except Exception as exc:  # noqa: BLE001 - provider isolation is the contract
                errors.append((provider_id, str(exc)))
        if cancelled:
            notices.append(("search", "جست‌وجو لغو شد؛ نتایج ممکن است ناقص باشد."))
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
            raise ProviderUnavailable(
                "کتابخانهٔ دانش v2 فعالی وجود ندارد؛ از مسیر Library → Upgrade Library to v2 آن را بسازید و تأیید کنید."
            )

        vault = KnowledgeVault(self._vault_path)
        try:
            _identity, accepted = vault.read_identity()
        except Exception as exc:  # noqa: BLE001 - convert vault parsing to provider state
            raise ProviderUnavailable(f"کتابخانهٔ دانش قابل خواندن نیست: {exc}") from exc
        if not accepted:
            raise ProviderUnavailable(
                "کتابخانهٔ دانش هنوز تأیید نهایی نشده است؛ مهاجرت را بازبینی و Accept کنید."
            )
        if not vault.index_path.is_file():
            raise ProviderUnavailable(
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
    """Deterministic placeholder; it never performs network I/O."""

    provider_id = "mock-online"
    source_label = "نمایشی — بدون اینترنت"

    def search(self, query: str, *, limit: int = 30) -> Sequence[SearchResult]:
        clean = " ".join(query.split())
        rows = (
            SearchResult(
                provider_id=self.provider_id,
                kind="datasheet",
                title=f"{clean} — نتیجهٔ نمایشی سازنده",
                subtitle="نمونهٔ رابط Phase 5؛ دادهٔ واقعی نیست",
                snippet="پیش‌نمایش و ذخیره برای منابع واقعی فعال است.",
                url=f"https://example.invalid/datasheets/{clean}",
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
                url=f"https://example.invalid/components/{clean}",
                can_preview=False,
                can_save=False,
                source_label=self.source_label,
            ),
        )
        return rows[: max(0, limit)]


def create_search_service(
    vault_path: str | Path | None,
    digikey_getter: object | None = None,
) -> SearchService:
    """Build the Phase 6 provider set (local + DigiKey + mock)."""

    digikey = DigiKeyProvider(digikey_getter) if digikey_getter is not None else DigiKeyProvider(
        lambda: None
    )
    return SearchService(
        (
            LocalKnowledgeProvider(vault_path),
            digikey,
            MockOnlineProvider(),
        )
    )


def create_phase5_search_service(vault_path: str | Path | None) -> SearchService:
    """Backward-compatible Phase 5 set (kept for existing tests/callers)."""

    return SearchService(
        (LocalKnowledgeProvider(vault_path), MockOnlineProvider())
    )
