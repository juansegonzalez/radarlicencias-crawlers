# Main listing photo extraction for Airbnb detail pages (hero DOM first, tightened JSON fallback).
import json
import re
from urllib.parse import urljoin, urlparse

# Substrings that must never be used as the main listing image (synthetic / platform assets).
BANNED_PICTURE_URL_SUBSTRINGS = (
    "AirbnbPlatformAssets",
    "Review-AI-Synthesis",
)


def is_banned_picture_url(url: str) -> bool:
    """True if URL should not be used as the primary listing image."""
    if not url or not isinstance(url, str):
        return True
    lower = url.lower()
    return any(b.lower() in lower for b in BANNED_PICTURE_URL_SUBSTRINGS)


def is_preferred_property_image_path(url: str) -> bool:
    """Likely real listing photo path on Airbnb CDN (not generic UI assets)."""
    if not url:
        return False
    try:
        path = urlparse(url).path.lower()
    except Exception:
        return False
    return "/im/pictures/" in path or "/im/photos/" in path


def _is_muscache_host(url: str) -> bool:
    try:
        host = urlparse(url).netloc.lower()
    except Exception:
        return False
    return host.endswith("muscache.com")


def _is_acceptable_listing_image(url: str) -> bool:
    if not url or not url.startswith("https://"):
        return False
    if is_banned_picture_url(url):
        return False
    if not _is_muscache_host(url):
        return False
    if not is_preferred_property_image_path(url):
        return False
    return True


def _json_unescape_string(s: str) -> str:
    try:
        return json.loads(f'"{s}"')
    except Exception:
        return s


def _img_url_from_img_selector(img) -> str:
    """Prefer data-original-uri, then https src on the same img node."""
    attrib = getattr(img, "attrib", None) or {}
    uri = attrib.get("data-original-uri") or attrib.get("data-original_uri")
    if uri:
        uri = uri.strip()
        if uri.startswith("https://"):
            return _json_unescape_string(uri) if "\\" in uri else uri
        if uri.startswith("//"):
            return "https:" + uri

    src = attrib.get("src") or ""
    src = src.strip()
    if not src:
        return ""
    if src.startswith("https://"):
        return src
    if src.startswith("//"):
        return "https:" + src
    if src.startswith("/"):
        return urljoin("https://www.airbnb.com/", src)
    return ""


def _extract_picture_url_from_hero_html(html_response) -> str:
    """
    Primary strategy: hero gallery under data-section-id="HERO_DEFAULT", DOM order.
    Prefer img[data-original-uri] first (display order), then other img src in that block.
    """
    if html_response is None:
        return ""
    hero = html_response.css('[data-section-id="HERO_DEFAULT"]')
    if not hero:
        return ""
    for img in hero.css("img[data-original-uri]"):
        candidate = _img_url_from_img_selector(img)
        if candidate and _is_acceptable_listing_image(candidate):
            return candidate
    for img in hero.css("img"):
        if img.attrib.get("data-original-uri") or img.attrib.get("data-original_uri"):
            continue
        candidate = _img_url_from_img_selector(img)
        if candidate and _is_acceptable_listing_image(candidate):
            return candidate
    return ""


def _extract_picture_url_from_page_original_uri(html_response) -> str:
    """
    Secondary DOM strategy: first acceptable img[data-original-uri] in document order
    (when hero block is missing or had no usable images).
    """
    if html_response is None:
        return ""
    for img in html_response.css("img[data-original-uri]"):
        candidate = _img_url_from_img_selector(img)
        if candidate and _is_acceptable_listing_image(candidate):
            return candidate
    return ""


# Tightened: do not match generic "url" keys (high false-positive rate).
_PAYLOAD_PICTURE_RE = re.compile(
    r'"(?:pictureUrl|picture_url|baseUrl)"\s*:\s*"(https://[^"]+)"'
)


def _extract_picture_url_from_payload(payload_text: str) -> str:
    """
    Last resort: scan embedded JSON for pictureUrl / picture_url / baseUrl only.
    Requires muscache host, preferred path, and banned-pattern rejection.
    """
    if not payload_text:
        return ""

    for m in _PAYLOAD_PICTURE_RE.finditer(payload_text):
        raw = m.group(1)
        url = _json_unescape_string(raw)
        if not url.startswith("https://"):
            continue
        if not _is_muscache_host(url):
            continue
        if is_banned_picture_url(url):
            continue
        if is_preferred_property_image_path(url):
            return url

    return ""


def extract_picture_url(html_response, payload_text: str) -> str:
    """
    Orchestrator: hero HTML -> page-wide data-original-uri -> tightened JSON scan.
    """
    url = _extract_picture_url_from_hero_html(html_response)
    if url:
        return url
    url = _extract_picture_url_from_page_original_uri(html_response)
    if url:
        return url
    return _extract_picture_url_from_payload(payload_text or "")
