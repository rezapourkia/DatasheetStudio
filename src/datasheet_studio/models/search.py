"""Domain types shared by search providers, coordination, and the strip.

Kept free of Qt, network, and storage imports so both ``services`` and
``infrastructure/web`` adapters can depend on it (see
``docs/modules/ONLINE_ADAPTER_FRAMEWORK.md`` §2).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, Sequence


@dataclass(frozen=True)
class SearchResult:
    """One normalized result from any local or online provider."""

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


class ProviderUnavailable(RuntimeError):
    """A provider is not configured/ready; shown as a notice, not an error."""


class SearchProvider(Protocol):
    """Small provider contract used by :class:`SearchService`."""

    provider_id: str

    def search(self, query: str, *, limit: int = 30) -> Sequence[SearchResult]: ...
