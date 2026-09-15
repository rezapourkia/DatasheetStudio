"""Online source adapters (official/permitted APIs only)."""

from datasheet_studio.infrastructure.web.http_client import (
    DownloadCancelledError,
    DownloadTooLargeError,
    DownloadedFile,
    HttpClient,
    HttpError,
    HttpRateLimitedError,
    HttpTimeoutError,
    InvalidPdfError,
)

__all__ = [
    "DownloadCancelledError",
    "DownloadTooLargeError",
    "DownloadedFile",
    "HttpClient",
    "HttpError",
    "HttpRateLimitedError",
    "HttpTimeoutError",
    "InvalidPdfError",
]
