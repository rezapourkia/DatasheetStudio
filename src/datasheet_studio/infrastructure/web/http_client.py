"""Bounded stdlib HTTP client for online sources.

All network access for adapters goes through this module so timeout, size,
cancellation, redirect, and error semantics live in one tested place.  The
transport is injectable so every behavior is unit-tested offline.
"""

from __future__ import annotations

import contextlib
from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
import socket
from typing import Any, Callable, Mapping
import urllib.error
import urllib.request

from datasheet_studio.models.search import ProviderUnavailable  # noqa: F401 (re-export)

DEFAULT_USER_AGENT = "DatasheetStudio/0.2 (desktop; +local engineering workspace)"
DEFAULT_JSON_LIMIT = 5 * 1024 * 1024  # 5 MB
DEFAULT_DOWNLOAD_LIMIT = 50 * 1024 * 1024  # 50 MB
_CHUNK = 64 * 1024

CancelCheck = Callable[[], bool]


class HttpError(RuntimeError):
    """A network request failed (status and message preserved)."""

    def __init__(self, message: str, status: int | None = None) -> None:
        super().__init__(message)
        self.status = status


class HttpTimeoutError(HttpError):
    """The request exceeded its timeout."""


class HttpRateLimitedError(HttpError):
    """The remote end answered with HTTP 429."""


class DownloadTooLargeError(HttpError):
    """The body exceeded the configured byte limit."""


class DownloadCancelledError(HttpError):
    """A cancellation check aborted the transfer."""


class InvalidPdfError(ValueError):
    """The payload does not start with the %PDF- signature."""


@dataclass(frozen=True)
class DownloadedFile:
    """A fully validated download on disk."""

    path: Path
    sha256: str
    size_bytes: int
    final_url: str
    content_type: str


class UrllibTransport:
    """Real network transport (stdlib only)."""

    def request(
        self,
        method: str,
        url: str,
        *,
        headers: Mapping[str, str],
        data: bytes | None = None,
        timeout: float = 30.0,
    ):
        request = urllib.request.Request(
            url, data=data, headers=dict(headers), method=method
        )
        try:
            return urllib.request.urlopen(request, timeout=timeout)
        except urllib.error.HTTPError as exc:
            if exc.code == 429:
                raise HttpRateLimitedError(
                    "محدودیت نرخ درخواست (HTTP 429)؛ کمی بعد دوباره تلاش کنید."
                ) from exc
            raise HttpError(f"خطای HTTP {exc.code} از منبع آنلاین.", status=exc.code) from exc
        except urllib.error.URLError as exc:
            if isinstance(exc.reason, (socket.timeout, TimeoutError)):
                raise HttpTimeoutError("مهلت پاسخ منبع آنلاین به پایان رسید.") from exc
            raise HttpError(f"ارتباط با منبع آنلاین برقرار نشد: {exc.reason}") from exc
        except (socket.timeout, TimeoutError) as exc:
            raise HttpTimeoutError("مهلت پاسخ منبع آنلاین به پایان رسید.") from exc


class HttpClient:
    """Small facade with JSON fetching and validated PDF downloads."""

    def __init__(
        self,
        transport: Any | None = None,
        user_agent: str = DEFAULT_USER_AGENT,
    ) -> None:
        self._transport = transport or UrllibTransport()
        self._user_agent = user_agent

    def fetch_json(
        self,
        method: str,
        url: str,
        *,
        headers: Mapping[str, str] | None = None,
        data: bytes | None = None,
        timeout: float = 20.0,
        cancel_check: CancelCheck | None = None,
        limit: int = DEFAULT_JSON_LIMIT,
    ) -> dict[str, Any]:
        merged = {"User-Agent": self._user_agent, "Accept": "application/json"}
        if headers:
            merged.update(dict(headers))
        response = self._transport.request(
            method, url, headers=merged, data=data, timeout=timeout
        )
        with contextlib.closing(response):
            status = int(getattr(response, "status", 200) or 200)
            body = self._read_capped(response, limit, cancel_check)
        if not 200 <= status < 300:
            raise HttpError(f"پاسخ غیرموفق HTTP {status}.", status=status)
        if not body:
            return {}
        try:
            parsed = json.loads(body.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise HttpError("پاسخ منبع آنلاین JSON معتبری نبود.") from exc
        if not isinstance(parsed, dict):
            raise HttpError("پاسخ JSON ساختار مورد انتظار را نداشت.")
        return parsed

    def download_file(
        self,
        url: str,
        destination: Path,
        *,
        max_bytes: int = DEFAULT_DOWNLOAD_LIMIT,
        expect_pdf: bool = True,
        cancel_check: CancelCheck | None = None,
        headers: Mapping[str, str] | None = None,
        timeout: float = 60.0,
    ) -> DownloadedFile:
        merged = {"User-Agent": self._user_agent}
        if headers:
            merged.update(dict(headers))
        response = self._transport.request(
            "GET", url, headers=merged, data=None, timeout=timeout
        )
        content_type = str(
            (getattr(response, "headers", None) or {}).get("Content-Type", "")
        )
        final_url = str(getattr(response, "url", "") or url)
        digest = hashlib.sha256()
        size = 0
        seen_signature = not expect_pdf
        destination.parent.mkdir(parents=True, exist_ok=True)
        try:
            with contextlib.closing(response), open(destination, "wb") as out:
                while True:
                    if cancel_check is not None and cancel_check():
                        raise DownloadCancelledError("دانلود توسط کاربر لغو شد.")
                    chunk = response.read(_CHUNK)
                    if not chunk:
                        break
                    size += len(chunk)
                    if size > max_bytes:
                        raise DownloadTooLargeError(
                            f"حجم فایل از سقف مجاز ({max_bytes // (1024 * 1024)} MB) بیشتر است."
                        )
                    if not seen_signature:
                        if not chunk.lstrip() .startswith(b"%PDF-"):
                            raise InvalidPdfError(
                                "محتوای دانلودشده یک PDF معتبر نیست."
                            )
                        seen_signature = True
                    digest.update(chunk)
                    out.write(chunk)
        except BaseException:
            with contextlib.suppress(OSError):
                destination.unlink()
            raise
        if expect_pdf and not seen_signature:
            raise InvalidPdfError("پاسخ خالی بود؛ فایل PDF دریافت نشد.")
        return DownloadedFile(
            path=destination,
            sha256=digest.hexdigest(),
            size_bytes=size,
            final_url=final_url,
            content_type=content_type,
        )

    @staticmethod
    def _read_capped(
        response: Any, limit: int, cancel_check: CancelCheck | None
    ) -> bytes:
        chunks: list[bytes] = []
        size = 0
        while True:
            if cancel_check is not None and cancel_check():
                raise DownloadCancelledError("درخواست توسط کاربر لغو شد.")
            chunk = response.read(_CHUNK)
            if not chunk:
                break
            size += len(chunk)
            if size > limit:
                raise DownloadTooLargeError("پاسخ منبع بزرگ‌تر از حد مجاز بود.")
            chunks.append(chunk)
        return b"".join(chunks)
