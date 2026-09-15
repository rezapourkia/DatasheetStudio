"""Offline tests for the bounded HTTP client (mocked transport)."""

import hashlib
import json
from pathlib import Path

import pytest

from datasheet_studio.infrastructure.web.http_client import (
    DownloadCancelledError,
    DownloadTooLargeError,
    HttpClient,
    HttpError,
    HttpRateLimitedError,
    HttpTimeoutError,
    InvalidPdfError,
)


class FakeResponse:
    def __init__(self, chunks, *, status=200, headers=None, url="https://final.example/f"):
        self._chunks = list(chunks)
        self.status = status
        self.headers = headers or {"Content-Type": "application/pdf"}
        self.url = url

    def read(self, size=-1):
        if not self._chunks:
            return b""
        return self._chunks.pop(0)

    def close(self):
        pass


class FakeTransport:
    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []

    def request(self, method, url, *, headers, data=None, timeout=30.0):
        self.calls.append((method, url, dict(headers), data))
        item = self.responses.pop(0)
        if isinstance(item, Exception):
            raise item
        return item


def test_fetch_json_follows_headers_and_parses():
    payload = {"Products": [{"ManPartNo": "DK124"}]}
    transport = FakeTransport(
        [FakeResponse([json.dumps(payload).encode()], headers={"Content-Type": "application/json"})]
    )
    client = HttpClient(transport)
    data = client.fetch_json("POST", "https://api.example/search", data=b"{}", headers={"X-Test": "1"})
    assert data["Products"][0]["ManPartNo"] == "DK124"
    method, url, headers, body = transport.calls[0]
    assert method == "POST" and body == b"{}"
    assert headers["X-Test"] == "1" and "User-Agent" in headers


def test_fetch_json_maps_429_and_timeout():
    client = HttpClient(FakeTransport([HttpRateLimitedError("rate limited")]))
    with pytest.raises(HttpRateLimitedError):
        client.fetch_json("GET", "https://api.example")

    client = HttpClient(FakeTransport([HttpTimeoutError("timeout")]))
    with pytest.raises(HttpTimeoutError):
        client.fetch_json("GET", "https://api.example")


def test_fetch_json_rejects_non_dict_and_malformed():
    client = HttpClient(FakeTransport([FakeResponse([b"[1,2,3]"])]))
    with pytest.raises(HttpError, match="ساختار"):
        client.fetch_json("GET", "https://api.example")

    client = HttpClient(FakeTransport([FakeResponse([b"{not json"])]))
    with pytest.raises(HttpError, match="JSON"):
        client.fetch_json("GET", "https://api.example")


def test_download_file_writes_valid_pdf_with_hash(tmp_path: Path):
    body = b"%PDF-1.7 fake content for tests"
    transport = FakeTransport([FakeResponse([body[:10], body[10:]])])
    client = HttpClient(transport)
    target = tmp_path / "out.pdf"

    downloaded = client.download_file("https://example.com/d.pdf", target)

    assert target.read_bytes() == body
    assert downloaded.sha256 == hashlib.sha256(body).hexdigest()
    assert downloaded.size_bytes == len(body)
    assert downloaded.final_url == "https://final.example/f"
    assert "pdf" in downloaded.content_type


def test_download_rejects_non_pdf_signature(tmp_path: Path):
    client = HttpClient(FakeTransport([FakeResponse([b"<html>not a pdf</html>"])]))
    with pytest.raises(InvalidPdfError):
        client.download_file("https://example.com/x.pdf", tmp_path / "x.pdf")
    assert not (tmp_path / "x.pdf").exists()


def test_download_aborts_when_too_large(tmp_path: Path):
    client = HttpClient(FakeTransport([FakeResponse([b"%PDF-1.7", b"x" * 100])]))
    with pytest.raises(DownloadTooLargeError):
        client.download_file(
            "https://example.com/big.pdf", tmp_path / "big.pdf", max_bytes=50
        )
    assert not (tmp_path / "big.pdf").exists()


def test_download_respects_cancellation(tmp_path: Path):
    client = HttpClient(FakeTransport([FakeResponse([b"%PDF-1.7", b"more"])]))
    with pytest.raises(DownloadCancelledError):
        client.download_file(
            "https://example.com/c.pdf",
            tmp_path / "c.pdf",
            cancel_check=lambda: True,
        )
    assert not (tmp_path / "c.pdf").exists()
