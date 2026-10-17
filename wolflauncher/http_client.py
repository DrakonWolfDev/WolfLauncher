"""Small, bounded HTTP helpers for read-only provider requests."""

from __future__ import annotations

import json
import random
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Any, Callable

from . import __version__
from .tls import https_context

DEFAULT_MAX_RESPONSE_BYTES = 2 * 1024 * 1024
JSON_CONTENT_TYPES = ("application/json", "application/problem+json")


@dataclass(frozen=True)
class HttpClientError(RuntimeError):
    """A safe, structured summary of a provider request failure."""

    category: str
    message: str
    status: int | None = None

    def __str__(self) -> str:
        return self.message


def user_agent() -> str:
    return f"WolfLauncher/{__version__}"


def fetch_json(
    url: str,
    *,
    timeout: float = 15.0,
    max_bytes: int = DEFAULT_MAX_RESPONSE_BYTES,
    cancel: Callable[[], bool] | None = None,
    retries: int = 1,
) -> Any:
    """Fetch one JSON document with bounded reads and transient GET retries."""
    return request_json(url, timeout=timeout, max_bytes=max_bytes, cancel=cancel, retries=retries)


def fetch_html(
    url: str, *, timeout: float = 15.0, max_bytes: int = DEFAULT_MAX_RESPONSE_BYTES
) -> str:
    """Fetch one bounded HTML document for a read-only provider fallback."""
    request = urllib.request.Request(
        url, headers={"User-Agent": user_agent(), "Accept": "text/html"}
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout, context=https_context()) as response:
            content_type = response.headers.get_content_type() if response.headers else ""
            if content_type and content_type not in {"text/html", "application/xhtml+xml"}:
                raise HttpClientError("content_type", "Provider returned non-HTML content")
            payload = _read_bounded(response, max_bytes, None)
    except urllib.error.HTTPError as exc:
        raise HttpClientError("http", f"Provider HTTP error: {exc.code}", exc.code) from exc
    except urllib.error.URLError as exc:
        raise HttpClientError("connection", f"Provider connection failed: {exc.reason}") from exc
    except TimeoutError as exc:
        raise HttpClientError("timeout", "Provider request timed out") from exc
    except OSError as exc:
        raise HttpClientError("connection", "Provider connection failed") from exc
    try:
        return payload.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise HttpClientError("invalid_text", "Provider returned invalid HTML") from exc


def post_form_json(
    url: str,
    fields: list[tuple[str, str]],
    *,
    timeout: float = 15.0,
    max_bytes: int = DEFAULT_MAX_RESPONSE_BYTES,
    cancel: Callable[[], bool] | None = None,
) -> Any:
    """POST form data once; non-idempotent requests are never retried."""
    from urllib.parse import urlencode

    return request_json(
        url,
        data=urlencode(fields).encode("ascii"),
        method="POST",
        timeout=timeout,
        max_bytes=max_bytes,
        cancel=cancel,
        retries=0,
    )


def post_json(
    url: str,
    payload: Any,
    *,
    timeout: float = 15.0,
    max_bytes: int = DEFAULT_MAX_RESPONSE_BYTES,
) -> Any:
    """Submit one bounded JSON document without retrying the write."""
    request = urllib.request.Request(
        url,
        data=json.dumps(payload, separators=(",", ":")).encode("utf-8"),
        headers={
            "User-Agent": user_agent(),
            "Accept": "application/json",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout, context=https_context()) as response:
            _validate_content_type(response)
            body = _read_bounded(response, max_bytes, None)
    except urllib.error.HTTPError as exc:
        raise HttpClientError("http", f"Provider HTTP error: {exc.code}", exc.code) from exc
    except urllib.error.URLError as exc:
        raise HttpClientError("connection", f"Provider connection failed: {exc.reason}") from exc
    except TimeoutError as exc:
        raise HttpClientError("timeout", "Provider request timed out") from exc
    except OSError as exc:
        raise HttpClientError("connection", "Provider connection failed") from exc
    try:
        return json.loads(body.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise HttpClientError("invalid_json", "Provider returned invalid JSON") from exc


def request_json(
    url: str,
    *,
    data: bytes | None = None,
    method: str | None = None,
    timeout: float = 15.0,
    max_bytes: int = DEFAULT_MAX_RESPONSE_BYTES,
    cancel: Callable[[], bool] | None = None,
    retries: int = 1,
) -> Any:
    """Perform a JSON request, retrying only idempotent GET failures."""
    headers = {"User-Agent": user_agent(), "Accept": "application/json"}
    if data is not None:
        headers["Content-Type"] = "application/x-www-form-urlencoded"
        retries = 0
    request = urllib.request.Request(url, data=data, headers=headers, method=method)
    attempts = max(0, retries) + 1
    for attempt in range(attempts):
        if cancel and cancel():
            raise HttpClientError("cancelled", "Request cancelled")
        try:
            with urllib.request.urlopen(
                request, timeout=timeout, context=https_context()
            ) as response:
                _validate_content_type(response)
                payload = _read_bounded(response, max_bytes, cancel)
            try:
                return json.loads(payload.decode("utf-8"))
            except (UnicodeDecodeError, json.JSONDecodeError) as exc:
                raise HttpClientError("invalid_json", "Provider returned invalid JSON") from exc
        except urllib.error.HTTPError as exc:
            if exc.code >= 500 and attempt + 1 < attempts:
                _retry_delay(attempt, cancel)
                continue
            raise HttpClientError("http", f"Provider HTTP error: {exc.code}", exc.code) from exc
        except urllib.error.URLError as exc:
            if attempt + 1 < attempts:
                _retry_delay(attempt, cancel)
                continue
            raise HttpClientError(
                "connection", f"Provider connection failed: {exc.reason}"
            ) from exc
        except TimeoutError as exc:
            if attempt + 1 < attempts:
                _retry_delay(attempt, cancel)
                continue
            raise HttpClientError("timeout", "Provider request timed out") from exc
        except OSError as exc:
            raise HttpClientError("connection", "Provider connection failed") from exc
    raise AssertionError("unreachable")


def _validate_content_type(response) -> None:
    headers = getattr(response, "headers", None)
    content_type = (
        headers.get_content_type() if headers and hasattr(headers, "get_content_type") else ""
    )
    if content_type and content_type not in JSON_CONTENT_TYPES:
        raise HttpClientError("content_type", "Provider returned a non-JSON response")


def _read_bounded(response, max_bytes: int, cancel: Callable[[], bool] | None) -> bytes:
    if max_bytes <= 0:
        raise ValueError("max_bytes must be positive")
    content_length = (
        getattr(response, "headers", {}).get("Content-Length")
        if getattr(response, "headers", None)
        else None
    )
    if content_length:
        try:
            if int(content_length) > max_bytes:
                raise HttpClientError("too_large", "Provider response exceeded the size limit")
        except ValueError:
            pass
    if cancel and cancel():
        raise HttpClientError("cancelled", "Request cancelled")
    payload = response.read(max_bytes + 1)
    if len(payload) > max_bytes:
        raise HttpClientError("too_large", "Provider response exceeded the size limit")
    return payload


def _retry_delay(attempt: int, cancel: Callable[[], bool] | None) -> None:
    if cancel and cancel():
        raise HttpClientError("cancelled", "Request cancelled")
    time.sleep(0.1 * (2**attempt) + random.uniform(0, 0.05))
