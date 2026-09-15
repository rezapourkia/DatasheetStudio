"""Official DigiKey Product Information v4 adapter (Phase 6).

Uses DigiKey's public keyword-search API with the OAuth2 client-credentials
flow.  Credentials are external configuration supplied by the caller and are
never stored here.  The real integration is UNTESTED: all behavior in this
repository is covered through a mocked HTTP transport
(``docs/modules/ONLINE_ADAPTER_FRAMEWORK.md`` §4).
"""

from __future__ import annotations

from dataclasses import dataclass
import json
import time
from typing import Callable, Sequence
from urllib.parse import urlencode

from datasheet_studio.infrastructure.web.http_client import HttpClient, HttpError
from datasheet_studio.models.search import ProviderUnavailable, SearchResult

TOKEN_URL = "https://api.digikey.com/v1/oauth2/token"
KEYWORD_SEARCH_URL = "https://api.digikey.com/products/v4/search/keyword"

# DigiKey tokens are typically valid ~15 minutes; refresh a minute early.
_TOKEN_REFRESH_MARGIN_S = 60.0


@dataclass(frozen=True)
class DigiKeyCredentials:
    client_id: str
    client_secret: str

    @property
    def is_complete(self) -> bool:
        return bool(self.client_id.strip() and self.client_secret.strip())


class DigiKeyProvider:
    """Search provider backed by DigiKey's official API."""

    provider_id = "digikey"
    source_label = "DigiKey · API رسمی"

    def __init__(
        self,
        credentials_getter: Callable[[], DigiKeyCredentials | None],
        http: HttpClient | None = None,
    ) -> None:
        self._credentials_getter = credentials_getter
        self._http = http or HttpClient()
        self._token: str | None = None
        self._token_expiry: float = 0.0

    # -- public API ---------------------------------------------------------

    def search(self, query: str, *, limit: int = 30) -> Sequence[SearchResult]:
        credentials = self._credentials_getter()
        if credentials is None or not credentials.is_complete:
            raise ProviderUnavailable(
                "DigiKey تنظیم نشده است؛ از Library → Online Sources Settings… "
                "کلیدها را وارد و فعال کنید."
            )
        token = self._fetch_token(credentials)
        payload = json.dumps(
            {"Keywords": query, "Limit": max(1, min(limit, 50)), "Offset": 0}
        ).encode("utf-8")
        data = self._http.fetch_json(
            "POST",
            KEYWORD_SEARCH_URL,
            headers=self._headers(credentials, token),
            data=payload,
        )
        return self._parse_products(query, data)

    def test_connection(self) -> str:
        """Fetch a token with the current credentials; raise on failure."""

        credentials = self._credentials_getter()
        if credentials is None or not credentials.is_complete:
            raise ProviderUnavailable(
                "کلاینت آی‌دی و کلید مخفی DigiKey را کامل وارد کنید."
            )
        self._token = None
        token = self._fetch_token(credentials)
        return f"اتصال موفق؛ توکن دریافت شد ({token[:8]}…)"

    # -- internals -----------------------------------------------------------

    def _headers(self, credentials: DigiKeyCredentials, token: str) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {token}",
            "X-DIGIKEY-Client-Id": credentials.client_id,
            "Content-Type": "application/json",
            "X-DIGIKEY-Locale-Site": "US",
            "X-DIGIKEY-Locale-Language": "en",
            "X-DIGIKEY-Locale-Currency": "USD",
        }

    def _fetch_token(self, credentials: DigiKeyCredentials) -> str:
        now = time.monotonic()
        if self._token and now < self._token_expiry - _TOKEN_REFRESH_MARGIN_S:
            return self._token
        body = urlencode(
            {
                "client_id": credentials.client_id,
                "client_password": credentials.client_secret,
                "grant_type": "client_credentials",
            }
        ).encode("utf-8")
        data = self._http.fetch_json(
            "POST",
            TOKEN_URL,
            headers={
                "Content-Type": "application/x-www-form-urlencoded",
            },
            data=body,
        )
        token = str(data.get("access_token", ""))
        if not token:
            raise HttpError("پاسخ توکن DigiKey فاقد access_token بود.")
        try:
            expires_in = float(data.get("expires_in", 900))
        except (TypeError, ValueError):
            expires_in = 900.0
        self._token = token
        self._token_expiry = time.monotonic() + max(60.0, expires_in)
        return token

    def _parse_products(
        self, query: str, data: dict
    ) -> list[SearchResult]:
        results: list[SearchResult] = []
        for product in data.get("Products", []) or []:
            variations = product.get("ProductVariations") or [{}]
            part_number = str(
                (variations[0] or {}).get("ManPartNo")
                or product.get("ProductDescription")
                or query
            ).strip() or query
            manufacturer = str(
                (product.get("Manufacturer") or {}).get("Name", "")
            ).strip()
            description = str(product.get("ProductDescription") or "").strip()
            datasheet_url = str(product.get("DatasheetUrl") or "").strip() or None
            product_url = str(product.get("ProductUrl") or "").strip() or None
            results.append(
                SearchResult(
                    provider_id=self.provider_id,
                    kind="datasheet",
                    title=part_number,
                    subtitle=manufacturer or "DigiKey",
                    snippet=description,
                    url=datasheet_url or product_url,
                    can_preview=bool(datasheet_url),
                    can_save=bool(datasheet_url),
                    source_label=self.source_label,
                )
            )
        return results
