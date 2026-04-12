# License pattern loading and registration number extraction for Airbnb (Mallorca).
# Registration text is in the initial HTML (description div); httpResponseBody is sufficient.
import logging
import os
import re

# Fallback when license_patterns.py is missing. All known prefixes (longer first so ETVPL beats ETV).
_BUILTIN_LICENSE_CODE = (
    r"(?:ETV60[/\-\s]*\d+|ETVPL[/\-\s]*\d+|GTOIB[/\-\s]*\d+|SBAL[/\-\s]*\d+|AVBAL[/\-\s]*\d+|"
    r"CTE[/\-\s]*\d+|ABT[/\-\s]*\d+|CTL[/\-\s]*\d+|CTC[/\-\s]*\d+|ETV[/\-\s]*\d+|"
    r"CR[/\-\s]*\d+|BC[/\-\s]*\d+|SF[/\-\s]*\d+|TA[/\-\s]*\d+|AT[/\-\s]*\d+|EE[/\-\s]*\d+|"
    r"MT[/\-\s]*\d+|CT[/\-\s]*\d+|CP[/\-\s]*\d+|CC[/\-\s]*\d+|TI[/\-\s]*\d+|AG[/\-\s]*\d+|"
    r"GT[/\-\s]*\d+|EH[/\-\s]*\d+|CE[/\-\s]*\d+|CA[/\-\s]*\d+|ETR[/\-\s]*\d+|HO[/\-\s]*\d+|"
    r"HR[/\-\s]*\d+|HA[/\-\s]*\d+|SB[/\-\s]*\d+|OC[/\-\s]*\d+|TC[/\-\s]*\d+|VT[/\-\s]*\d+|"
    r"BCP[/\-\s]*\d+|D[/\-\s]*\d+|R[/\-\s]*\d+|H[/\-\s]*\d+|C[/\-\s]*\d+|B[/\-\s]*\d+)"
)

_log = logging.getLogger(__name__)

# Provenance for extract_registration_number_with_source (feeds / audits).
REGISTRATION_SOURCE_NONE = "none"
REGISTRATION_SOURCE_MALLORCA_REGIONAL_LABEL = "mallorca_regional_label"
REGISTRATION_SOURCE_DESCRIPTION_STANDALONE = "description_standalone"
REGISTRATION_SOURCE_SPAIN_NATIONAL_DERIVED = "spain_national_derived"


def get_license_code() -> str:
    """Return LICENSE_CODE regex string from data/license_patterns.py or built-in. Log warning on load failure."""
    path = os.path.join(os.path.dirname(__file__), "..", "data", "license_patterns.py")
    if os.path.isfile(path):
        try:
            import importlib.util

            spec = importlib.util.spec_from_file_location("license_patterns", path)
            if spec and spec.loader:
                mod = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(mod)
                return getattr(mod, "LICENSE_CODE", _BUILTIN_LICENSE_CODE)
        except Exception as e:
            _log.warning(
                "Could not load license_patterns.py: %s; using built-in patterns.",
                e,
                exc_info=False,
            )
    return _BUILTIN_LICENSE_CODE


def _compile_patterns(license_code: str) -> tuple:
    """Build registration regexes from LICENSE_CODE string.

    These patterns are run on a *normalized* version of the page payload where Airbnb's embedded
    HTML/JSON line breaks (\"\\u003cbr\" and \"<br\") are converted into real newlines.

    This makes extraction much more reliable and avoids accidentally matching license-like tokens
    inside the long national registration string.
    """

    dash = r"(?:-|–|—)"

    mallorca_regional = re.compile(
        r"Mallorca\\s*"
        + dash
        + r"\\s*Regional\\s*registration\\s*number"
        + r"[^\S\n]*"
        + "\n+"
        + r"[^\S\n]*("
        + license_code
        + r")",
        re.IGNORECASE,
    )
    mallorca_regional_alt = re.compile(
        r"Mallorca\\s+Regional\\s+Registration\\s+Number\\s*[:\\s]*"
        + r"[^\S\n]*"
        + "\n+"
        + r"[^\S\n]*("
        + license_code
        + r")",
        re.IGNORECASE,
    )
    registration_details = re.compile(
        r"Registration\\s+Details[\\s\\S]{0,1500}?"
        r"Regional\\s*registration\\s*number"
        + r"[^\S\n]*"
        + "\n+"
        + r"[^\S\n]*("
        + license_code
        + r")",
        re.IGNORECASE,
    )

    return (mallorca_regional, mallorca_regional_alt, registration_details)


_LICENSE_CODE = get_license_code()
_REGISTRATION_PATTERNS = _compile_patterns(_LICENSE_CODE)
_LICENSE_TOKEN_RE = re.compile(_LICENSE_CODE, re.IGNORECASE)
_MALLORCA_REGIONAL_LABEL_RE = re.compile(
    r"Mallorca\s*(?:-|–|—)\s*Regional\s*registration\s*number",
    re.IGNORECASE,
)

_STANDALONE_ETV_RE = re.compile(
    r"(?<![A-Za-z0-9])(?:ETVPL|ETV)[/\-\s]*(\d{2,6})(?!\d)",
    re.IGNORECASE,
)

_SPAIN_NAT_ETV_RE = re.compile(
    r"ESFCTU[\d\s]{5,}?(ETVPL|ETV)[/\-\s]*(\d{3,})",
    re.IGNORECASE,
)


def _normalize_br(text: str) -> str:
    """Normalize Airbnb's escaped HTML (<br>) markers to newlines."""
    return re.sub(r"(?:[\\\\]u003cbr\s*/?>|<br\s*/?>)", "\n", text, flags=re.IGNORECASE)


def extract_registration_number_with_source(
    text: str, description_text: str = ""
) -> tuple[str, str]:
    """Extract Mallorca registration number and how it was obtained.

    Priority (unchanged from extract_registration_number):
    1. Explicit Mallorca regional registration block / structured patterns (authoritative).
    2. Standalone ETV/ETVPL in description or page text (not inside Spain national blob).
    3. Spain national registration string — lowest priority recovery path.

    Returns:
        (normalized_registration_or_empty, one of REGISTRATION_SOURCE_* constants).
    """
    if not text and not description_text:
        return "", REGISTRATION_SOURCE_NONE

    t = _normalize_br(text) if text else ""

    # --- Strategy 1: Mallorca Regional label and structured blocks ---
    if t:
        m = _MALLORCA_REGIONAL_LABEL_RE.search(t)
        if m:
            after = t[m.end() : m.end() + 250]
            tok = _LICENSE_TOKEN_RE.search(after)
            if tok:
                return normalize_registration(tok.group(0)), REGISTRATION_SOURCE_MALLORCA_REGIONAL_LABEL

        for pattern in _REGISTRATION_PATTERNS:
            m2 = pattern.search(t)
            if m2:
                return normalize_registration(m2.group(1)), REGISTRATION_SOURCE_MALLORCA_REGIONAL_LABEL

    # --- Strategy 2: Standalone ETV/ETVPL (prefer description when provided) ---
    search_text = description_text or t
    result = _extract_standalone_etv(search_text)
    if result:
        return result, REGISTRATION_SOURCE_DESCRIPTION_STANDALONE

    # --- Strategy 3: Spain national (recovery only) ---
    result = _extract_from_spain_national(search_text)
    if result:
        return result, REGISTRATION_SOURCE_SPAIN_NATIONAL_DERIVED

    if description_text and search_text != t and t:
        result = _extract_standalone_etv(t)
        if result:
            return result, REGISTRATION_SOURCE_DESCRIPTION_STANDALONE
        result = _extract_from_spain_national(t)
        if result:
            return result, REGISTRATION_SOURCE_SPAIN_NATIONAL_DERIVED

    return "", REGISTRATION_SOURCE_NONE


def extract_registration_number(text: str, description_text: str = "") -> str:
    """Extract Mallorca registration number from page text. Returns normalized string or empty.

    Same logic as extract_registration_number_with_source but discards provenance.
    """
    reg, _ = extract_registration_number_with_source(text, description_text)
    return reg


def _extract_standalone_etv(text: str) -> str:
    """Find a standalone ETV/ETVPL token not embedded inside a Spain national registration string."""
    if not text:
        return ""
    for m in _STANDALONE_ETV_RE.finditer(text):
        start = max(0, m.start() - 60)
        preceding = text[start:m.start()]
        if re.search(r"ESFCTU[\d\s]{5,}$", preceding, re.IGNORECASE):
            continue
        return normalize_registration(m.group(0))
    return ""


def _extract_from_spain_national(text: str) -> str:
    """Extract license from Spain national registration number by dropping the last digit.

    Pattern: ESFCTU<long digits>(ETV|ETVPL)/<number><extra_digit>
    The actual license is the prefix + number without the trailing digit.
    """
    if not text:
        return ""
    m = _SPAIN_NAT_ETV_RE.search(text)
    if m:
        prefix = m.group(1).upper()
        digits = m.group(2)
        if len(digits) >= 2:
            license_digits = digits[:-1]
            return f"{prefix}/{license_digits}"
    return ""


def normalize_registration(raw: str) -> str:
    """Normalize to consistent form: PREFIX/number (slash, no spaces) for any license code."""
    if not raw:
        return ""
    s = raw.strip().replace(" ", "")
    # When there's a separator (/, -, or space in original), allow digits in prefix (e.g. ETV60/789)
    m = re.match(r"^([A-Za-z]+\d*)[/\-\s]+(\d+)", s)
    if m:
        prefix, num = m.group(1), m.group(2)
        return f"{prefix.upper()}/{num}"
    # No separator: letters then digits (e.g. ETV123 -> ETV/123)
    m = re.match(r"^([A-Za-z]+)(\d+)$", s)
    if m:
        return f"{m.group(1).upper()}/{m.group(2)}"
    return s
