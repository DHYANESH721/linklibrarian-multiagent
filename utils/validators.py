"""URL validation and normalization helpers."""

import ipaddress
import re
from urllib.parse import urlparse, urlunparse

_TRACKING_PARAMS = re.compile(
    r"^(utm_[a-z]+|fbclid|gclid|mc_eid|igshid|ref_src)$", re.IGNORECASE
)


class ValidationError(ValueError):
    """Raised when user input cannot be used."""


def normalize_url(raw_url: str) -> str:
    """Clean a user-supplied URL: add scheme, drop tracking params and fragments.

    Raises:
        ValidationError: if the URL is empty, malformed, or not http(s).
    """
    if not raw_url or not raw_url.strip():
        raise ValidationError("Enter a URL to save.")

    url = raw_url.strip()
    if "://" not in url:
        url = "https://" + url

    parsed = urlparse(url)

    if parsed.scheme not in {"http", "https"}:
        raise ValidationError("Only http and https links can be saved.")
    if not parsed.netloc or "." not in parsed.netloc.split(":")[0]:
        raise ValidationError("That does not look like a valid web address.")
    if _is_private_host(parsed.hostname):
        raise ValidationError("Local and private network addresses cannot be saved.")

    query = "&".join(
        part
        for part in parsed.query.split("&")
        if part and not _TRACKING_PARAMS.match(part.split("=")[0])
    )
    path = parsed.path.rstrip("/") or "/"

    return urlunparse(
        (parsed.scheme, parsed.netloc.lower(), path, parsed.params, query, "")
    )


def _is_private_host(hostname: str | None) -> bool:
    """Block localhost and RFC1918 targets (basic SSRF guard)."""
    if not hostname:
        return True
    if hostname.lower() in {"localhost", "127.0.0.1", "0.0.0.0", "::1"}:
        return True
    try:
        return ipaddress.ip_address(hostname).is_private
    except ValueError:
        return False


def clean_text(value: str | None, max_length: int = 512) -> str:
    """Collapse whitespace and truncate a free-text field."""
    if not value:
        return ""
    collapsed = re.sub(r"\s+", " ", str(value)).strip()
    return collapsed[:max_length]
