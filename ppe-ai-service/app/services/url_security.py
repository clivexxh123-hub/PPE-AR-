import ipaddress
import socket
from typing import Any
from urllib.parse import urlparse


_SENSITIVE_FIELD_NAMES = {
    "authorization",
    "cookie",
    "xapikey",
    "requiredheaders",
}


class UnsafeUrlError(ValueError):
    """Raised when a network URL targets a local or private address."""


def _normalized_name(name: Any) -> str:
    return str(name).lower().replace("-", "").replace("_", "")


def redact_headers(headers: dict[str, Any] | None) -> dict[str, str]:
    """Keep header names while removing every header value from metadata."""
    if not isinstance(headers, dict):
        return {}
    return {str(key): "[REDACTED]" for key in headers}


def redact_sensitive_data(value: Any) -> Any:
    """Recursively redact sensitive header fields before persisting metadata."""
    if isinstance(value, dict):
        redacted: dict[Any, Any] = {}
        for key, item in value.items():
            normalized = _normalized_name(key)
            if normalized == "requiredheaders":
                redacted[key] = redact_headers(item)
            elif normalized in _SENSITIVE_FIELD_NAMES:
                redacted[key] = "[REDACTED]"
            else:
                redacted[key] = redact_sensitive_data(item)
        return redacted
    if isinstance(value, list):
        return [redact_sensitive_data(item) for item in value]
    return value


def _resolved_addresses(hostname: str, port: int | None) -> set[ipaddress.IPv4Address | ipaddress.IPv6Address]:
    try:
        return {ipaddress.ip_address(hostname)}
    except ValueError:
        pass

    try:
        infos = socket.getaddrinfo(hostname, port, type=socket.SOCK_STREAM)
    except (OSError, socket.gaierror) as exc:
        raise UnsafeUrlError("URL hostname could not be resolved") from exc

    addresses: set[ipaddress.IPv4Address | ipaddress.IPv6Address] = set()
    for info in infos:
        try:
            addresses.add(ipaddress.ip_address(info[4][0]))
        except (IndexError, ValueError):
            continue
    if not addresses:
        raise UnsafeUrlError("URL hostname has no resolved address")
    return addresses


def validate_public_http_url(url: str, purpose: str = "URL") -> None:
    """Reject HTTP(S) URLs that resolve to loopback, private, or local networks."""
    parsed = urlparse(str(url).strip())
    if parsed.scheme.lower() not in {"http", "https"}:
        raise UnsafeUrlError(f"{purpose} must use HTTP or HTTPS")
    if parsed.username or parsed.password:
        raise UnsafeUrlError(f"{purpose} must not contain credentials")
    hostname = parsed.hostname
    if not hostname:
        raise UnsafeUrlError(f"{purpose} hostname is missing")

    normalized_host = hostname.rstrip(".").lower()
    if normalized_host in {"localhost", "localhost.localdomain"}:
        raise UnsafeUrlError(f"{purpose} cannot target localhost")

    try:
        port = parsed.port
    except ValueError as exc:
        raise UnsafeUrlError(f"{purpose} port is invalid") from exc

    for address in _resolved_addresses(normalized_host, port):
        if (
            address.is_loopback
            or address.is_private
            or address.is_link_local
            or address.is_unspecified
            or address.is_reserved
            or not address.is_global
        ):
            raise UnsafeUrlError(f"{purpose} cannot target a local or private address")
