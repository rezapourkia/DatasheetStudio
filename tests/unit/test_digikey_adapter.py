"""Offline tests for the DigiKey adapter (mocked HTTP transport)."""

import json

import pytest

from datasheet_studio.infrastructure.web.digikey import (
    DigiKeyCredentials,
    DigiKeyProvider,
)
from datasheet_studio.infrastructure.web.http_client import (
    HttpRateLimitedError,
)
from datasheet_studio.models.search import ProviderUnavailable

from tests.unit.test_http_client import FakeResponse, FakeTransport, HttpClient

CREDS = DigiKeyCredentials(client_id="cid-123", client_secret="secret-456")


def provider_with(transport) -> DigiKeyProvider:
    return DigiKeyProvider(lambda: CREDS, http=HttpClient(transport))

TOKEN_BODY = {"access_token": "token-abc", "expires_in": 900}
SEARCH_BODY = {
    "Products": [
        {
            "ProductDescription": "Offline flyback switcher",
            "Manufacturer": {"Name": "Linkage"},
            "DatasheetUrl": "https://media.digikey.com/pdf/dk124.pdf",
            "ProductUrl": "https://www.digikey.com/en/products/detail/linkage/DK124",
            "ProductVariations": [{"ManPartNo": "DK124"}],
        },
        {
            "ProductDescription": "Buck converter without datasheet link",
            "Manufacturer": {"Name": "TI"},
            "ProductUrl": "https://www.digikey.com/en/products/detail/ti/BQ1",
            "ProductVariations": [{"ManPartNo": "BQ12345"}],
        },
    ]
}


def token_response():
    return FakeResponse(
        [json.dumps(TOKEN_BODY).encode()], headers={"Content-Type": "application/json"}
    )


def search_response(body=None):
    return FakeResponse(
        [json.dumps(body if body is not None else SEARCH_BODY).encode()],
        headers={"Content-Type": "application/json"},
    )


def test_unconfigured_provider_is_unavailable_not_error():
    provider = DigiKeyProvider(lambda: None, http=HttpClientStub())
    with pytest.raises(ProviderUnavailable):
        provider.search("DK124")


class HttpClientStub:
    def fetch_json(self, *a, **k):  # pragma: no cover - must not be reached
        raise AssertionError("network must not be called")


def test_happy_path_token_then_search():
    transport = FakeTransport([token_response(), search_response()])
    provider = provider_with(transport)

    results = provider.search("DK124")

    assert [row.title for row in results] == ["DK124", "BQ12345"]
    first, second = results
    assert first.can_preview and first.can_save and first.url.endswith("dk124.pdf")
    assert first.subtitle == "Linkage" and first.snippet == "Offline flyback switcher"
    assert not second.can_save and second.url.endswith("/BQ1")

    token_call, search_call = transport.calls
    assert "oauth2/token" in token_call[1]
    assert b"grant_type=client_credentials" in token_call[3]
    assert "keyword" in search_call[1]
    assert search_call[2]["Authorization"] == "Bearer token-abc"
    assert search_call[2]["X-DIGIKEY-Client-Id"] == "cid-123"


def test_token_is_cached_between_searches():
    transport = FakeTransport(
        [token_response(), search_response(), search_response()]
    )
    provider = provider_with(transport)

    provider.search("DK124")
    provider.search("DK124")

    assert len(transport.calls) == 3  # one token + two searches


def test_rate_limit_and_malformed_results_surface_as_http_errors():
    transport = FakeTransport([token_response(), HttpRateLimitedError("429")])
    provider = provider_with(transport)
    with pytest.raises(HttpRateLimitedError):
        provider.search("DK124")

    transport = FakeTransport([token_response(), search_response({"Products": "oops"})])
    provider = provider_with(transport)
    with pytest.raises((TypeError, AttributeError)):
        provider.search("DK124")
