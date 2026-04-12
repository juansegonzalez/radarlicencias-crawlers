# Spider: Airbnb — Mallorca listings only.
# Run monthly. Cheapest viable strategy: browserHtml for list/pagination (Airbnb loads search results via JS, so HTTP returns no links);
# httpResponseBody for detail (registration text is in the initial HTML, no "Show more" needed).
# See docs/AIRBNB_MALLORCA_ENTRY_POINT.md for search URL / pagination context.

import json
import os
import re
import scrapy
import base64
from scrapy.exceptions import NotSupported
from scrapy.http import HtmlResponse
from urllib.parse import quote, urljoin
from radarlicencias.items import AirbnbListingItem
from radarlicencias.extractors import extract_registration_number
from radarlicencias.extractors.airbnb_picture import extract_picture_url

# Mallorca bounding box (rough). Used as the root node for quadtree discovery.
MALLORCA_SW_LAT = 39.200
MALLORCA_SW_LNG = 2.300
MALLORCA_NE_LAT = 39.980
MALLORCA_NE_LNG = 3.480

# Quadtree limits: stop splitting when boxes get too small (lat/lng span).
MIN_CELL_LAT_SPAN = 0.01
MIN_CELL_LNG_SPAN = 0.01

# StaysSearch JSON page size (what we saw in HAR / tests).
STAYSSEARCH_PAGE_SIZE = 18

# StaysSearch persisted query hash (part of the /api/v3/StaysSearch/<hash> URL).
# If Airbnb deploys a new frontend and discovery starts failing with 400 errors,
# grab the current StaysSearch URL from DevTools and update this value.
STAYSSEARCH_HASH = "69c7ba9c6afd2e7838cb48a35297497760e93fb84331303c79b38f6d1d7085bc"

# Public Airbnb web GraphQL API key (seen in StaysSearch requests).
AIRBNB_WEB_API_KEY = "d306zoyjsyarp7ifhu67rjxn52tv0t20"


# Location shown on listing page (e.g. "Palma, Spain") — usually above the map.
# Match "Place, Spain" or "Place, Illes Balears, Spain" or "Place, Balearic Islands" in HTML.
LOCATION_PATTERN = re.compile(
    r">\s*([^<>]{2,80},\s*(?:Spain|Illes Balears|Balearic Islands))\s*<",
    re.IGNORECASE,
)
LOCATION_ATTR_PATTERN = re.compile(
    r'["\']([^"\']{2,80},\s*(?:Spain|Illes Balears|Balearic Islands))["\']',
    re.IGNORECASE,
)

# Path to the 53 Mallorca municipalities list (one per line). Used when running locally.
# On Scrapy Cloud the data file is often not included in the deployed egg, so we fall back to MALLORCA_MUNICIPALITIES below.
_DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data")
_MUNICIPALITIES_FILE = os.path.join(_DATA_DIR, "mallorca_municipalities.txt")
_SEARCH_REGIONS_FILE = os.path.join(_DATA_DIR, "search_regions_mallorca.txt")

# Built-in list of 53 Mallorca municipalities (official). Used when the data file is missing (e.g. on Scrapy Cloud).
# Keep in sync with radarlicencias/data/mallorca_municipalities.txt.
MALLORCA_MUNICIPALITIES = (
    "Alaró",
    "Alcúdia",
    "Algaida",
    "Andratx",
    "Ariany",
    "Artà",
    "Banyalbufar",
    "Binissalem",
    "Búger",
    "Bunyola",
    "Calvià",
    "Campanet",
    "Campos",
    "Capdepera",
    "Consell",
    "Costitx",
    "Deià",
    "Escorca",
    "Esporles",
    "Estellencs",
    "Felanitx",
    "Fornalutx",
    "Inca",
    "Lloret de Vistalegre",
    "Lloseta",
    "Llubí",
    "Llucmajor",
    "Manacor",
    "Mancor de la Vall",
    "Maria de la Salut",
    "Marratxí",
    "Montuïri",
    "Muro",
    "Palma",
    "Petra",
    "Sa Pobla",
    "Pollença",
    "Porreres",
    "Puigpunyent",
    "Ses Salines",
    "Sant Joan",
    "Sant Llorenç des Cardassar",
    "Santa Eugènia",
    "Santa Margalida",
    "Santa Maria del Camí",
    "Santanyí",
    "Selva",
    "Sencelles",
    "Sineu",
    "Sóller",
    "Son Servera",
    "Valldemossa",
    "Vilafranca de Bonany",
)

# Built-in extra search regions (towns/areas) when data file is missing on Scrapy Cloud. Keep in sync with data/search_regions_mallorca.txt.
SEARCH_REGIONS_BUILTIN = (
    ("Magaluf", "Calvià"),
    ("Palmanova", "Calvià"),
    ("Santa Ponça", "Calvià"),
    ("Peguera", "Calvià"),
    ("Portals Nous", "Calvià"),
    ("Bendinat", "Calvià"),
    ("Costa d'en Blanes", "Calvià"),
    ("Illetes", "Calvià"),
    ("S'Illeta", "Calvià"),
    ("Costa de la Calma", "Calvià"),
    ("Son Ferrer", "Calvià"),
    ("Cala Vinyes", "Calvià"),
    ("Galatzó", "Calvià"),
    ("Calvià", "Calvià"),
    ("Palma de Mallorca", "Palma"),
    ("El Terreno", "Palma"),
    ("Portopi", "Palma"),
    ("Cala Major", "Palma"),
    ("Playa de Palma", "Palma"),
    ("Can Pastilla", "Palma"),
    ("S'Arenal", "Palma"),
    ("Es Molinar", "Palma"),
    ("Son Armadams", "Palma"),
    ("Es Portixol", "Palma"),
    ("Coll d'en Rabassa", "Palma"),
    ("Gènova", "Palma"),
    ("Es Secar de la Real", "Palma"),
    ("Son Vida", "Palma"),
    ("Port de Sóller", "Sóller"),
    ("Sóller", "Sóller"),
    ("Biniaraix", "Sóller"),
    ("Fornalutx", "Fornalutx"),
    ("Deià", "Deià"),
    ("Valldemossa", "Valldemossa"),
    ("Banyalbufar", "Banyalbufar"),
    ("Estellencs", "Estellencs"),
    ("Esporles", "Esporles"),
    ("Port de Pollença", "Pollença"),
    ("Cala Sant Vicenç", "Pollença"),
    ("Pollença", "Pollença"),
    ("El Pinaret", "Pollença"),
    ("Cala Carbó", "Pollença"),
    ("Port d'Alcúdia", "Alcúdia"),
    ("Alcúdia", "Alcúdia"),
    ("Mal Pas", "Alcúdia"),
    ("Bonaire", "Alcúdia"),
    ("Alcanada", "Alcúdia"),
    ("Muro", "Muro"),
    ("Playa de Muro", "Muro"),
    ("Can Picafort", "Santa Margalida"),
    ("Santa Margalida", "Santa Margalida"),
    ("Cala Agulla", "Capdepera"),
    ("Cala Mesquida", "Capdepera"),
    ("Cala Gat", "Capdepera"),
    ("Canyamel", "Capdepera"),
    ("Cala Millor", "Sant Llorenç des Cardassar"),
    ("Sant Llorenç des Cardassar", "Sant Llorenç des Cardassar"),
    ("Cala Bona", "Son Servera"),
    ("Son Servera", "Son Servera"),
    ("Cala Bona", "Sant Llorenç des Cardassar"),
    ("S'Illot", "Sant Llorenç des Cardassar"),
    ("Porto Cristo", "Manacor"),
    ("Manacor", "Manacor"),
    ("Cales de Mallorca", "Manacor"),
    ("Cala Murada", "Manacor"),
    ("S'Illot", "Manacor"),
    ("Cala Ratjada", "Capdepera"),
    ("Capdepera", "Capdepera"),
    ("Artà", "Artà"),
    ("Cala Torta", "Artà"),
    ("Cala d'Or", "Santanyí"),
    ("Santanyí", "Santanyí"),
    ("Cala Figuera", "Santanyí"),
    ("Cala Santanyí", "Santanyí"),
    ("Cala Llombards", "Santanyí"),
    ("Cala Mondrago", "Santanyí"),
    ("S'Alqueria Blanca", "Santanyí"),
    ("Porto Petro", "Santanyí"),
    ("Colonia de Sant Jordi", "Ses Salines"),
    ("Ses Salines", "Ses Salines"),
    ("Campos", "Campos"),
    ("Sa Ràpita", "Campos"),
    ("Llucmajor", "Llucmajor"),
    ("S'Arenal", "Llucmajor"),
    ("Cala Pi", "Llucmajor"),
    ("Felanitx", "Felanitx"),
    ("Porto Colom", "Felanitx"),
    ("Cala Serena", "Felanitx"),
    ("Port d'Andratx", "Andratx"),
    ("Andratx", "Andratx"),
    ("S'Arracó", "Andratx"),
    ("Sant Elm", "Andratx"),
    ("Cala Egos", "Andratx"),
    ("Sa Pobla", "Sa Pobla"),
    ("Mancor de la Vall", "Mancor de la Vall"),
    ("Inca", "Inca"),
    ("Binissalem", "Binissalem"),
    ("Consell", "Consell"),
    ("Santa Maria del Camí", "Santa Maria del Camí"),
    ("Marratxí", "Marratxí"),
    ("Pòrtol", "Marratxí"),
    ("Bunyola", "Bunyola"),
    ("Puigpunyent", "Puigpunyent"),
    ("Alaró", "Alaró"),
    ("Lloseta", "Lloseta"),
    ("Campanet", "Campanet"),
    ("Selva", "Selva"),
    ("Escorca", "Escorca"),
    ("Sineu", "Sineu"),
    ("Montuïri", "Montuïri"),
    ("Porreres", "Porreres"),
    ("Sant Joan", "Sant Joan"),
    ("Vilafranca de Bonany", "Vilafranca de Bonany"),
    ("Petra", "Petra"),
    ("Llubí", "Llubí"),
    ("Sencelles", "Sencelles"),
    ("Santa Eugènia", "Santa Eugènia"),
    ("Algaida", "Algaida"),
    ("Lloret de Vistalegre", "Lloret de Vistalegre"),
    ("Costitx", "Costitx"),
    ("Maria de la Salut", "Maria de la Salut"),
    ("Ariany", "Ariany"),
    ("Búger", "Búger"),
)


def _load_municipalities():
    """Load municipality names: from data file if present, else use built-in list (e.g. on Scrapy Cloud)."""
    if os.path.isfile(_MUNICIPALITIES_FILE):
        try:
            with open(_MUNICIPALITIES_FILE, encoding="utf-8") as f:
                names = [
                    line.strip()
                    for line in f
                    if line.strip() and not line.strip().startswith("#")
                ]
                if names:
                    return names
        except OSError:
            pass
    return list(MALLORCA_MUNICIPALITIES)


def _load_search_regions():
    """
    Load finer-grained search regions (towns / neighbourhoods) mapped to municipalities.
    File format (UTF-8): search_term|municipality, one per line, '#' = comment.
    Returns list of (search_term, municipality). Uses SEARCH_REGIONS_BUILTIN when file is missing (e.g. on Scrapy Cloud).
    """
    regions = []
    if os.path.isfile(_SEARCH_REGIONS_FILE):
        try:
            with open(_SEARCH_REGIONS_FILE, encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line or line.startswith("#"):
                        continue
                    if "|" in line:
                        search_term, municipality = [part.strip() for part in line.split("|", 1)]
                        if search_term and municipality:
                            regions.append((search_term, municipality))
        except OSError:
            pass
    if not regions:
        regions = list(SEARCH_REGIONS_BUILTIN)
    return regions


def _search_url_for_municipality(search_term: str, items_offset: int = 0) -> str:
    """Build Airbnb search URL for a place name (municipality, town, etc.). Paginate with items_offset."""
    # Airbnb path: /s/PlaceName--Spain/homes. Hyphens for spaces; encode accents.
    segment = search_term.replace(" ", "-") + "--Spain"
    path = quote(segment, safe="-")
    base = f"https://www.airbnb.com/s/{path}/homes"
    return f"{base}?refinement_paths[]=/homes&items_offset={items_offset}"


def _search_url_for_bbox(
    sw_lat: float,
    sw_lng: float,
    ne_lat: float,
    ne_lng: float,
    items_offset: int = 0,
    checkin: str | None = None,
    checkout: str | None = None,
) -> str:
    """Build Airbnb search URL for a map bounding box (search_by_map)."""
    # Anchor to Mallorca to avoid Airbnb drifting to other regions.
    base = "https://www.airbnb.com/s/Mallorca--Spain/homes"
    url = (
        f"{base}?refinement_paths[]=/homes"
        f"&search_by_map=true"
        f"&sw_lat={sw_lat:.6f}&sw_lng={sw_lng:.6f}"
        f"&ne_lat={ne_lat:.6f}&ne_lng={ne_lng:.6f}"
        f"&items_offset={items_offset}"
    )
    if checkin and checkout:
        url += f"&checkin={checkin}&checkout={checkout}&adults=1"
    return url


def _stayssearch_url() -> str:
    """
    Build the StaysSearch persisted-query URL.
    """
    return f"https://www.airbnb.com/api/v3/StaysSearch/{STAYSSEARCH_HASH}?operationName=StaysSearch&locale=en&currency=EUR"


def _build_stayssearch_payload(
    sw_lat: float,
    sw_lng: float,
    ne_lat: float,
    ne_lng: float,
) -> dict:
    """
    StaysSearch payload for a single map move over a bbox.

    This is based on a working payload captured from the Airbnb web UI.
    We keep most parameters stable and only substitute the bbox coordinates.
    """
    # Flags captured from the working request. These may change over time.
    treatment_flags = [
        "feed_map_decouple_m11_treatment",
        "recommended_amenities_2024_treatment_b",
        "filter_redesign_2024_treatment",
        "filter_reordering_2024_roomtype_treatment",
        "p2_category_bar_removal_treatment",
        "selected_filters_2024_treatment",
        "recommended_filters_2024_treatment_b",
        "m13_search_input_phase2_treatment",
        "m13_search_input_services_enabled",
        "m13_2025_experiences_p2_treatment",
    ]

    raw_params_common: list[dict] = [
        {"filterName": "cdnCacheSafe", "filterValues": ["false"]},
        {"filterName": "channel", "filterValues": ["EXPLORE"]},
        {"filterName": "flexibleTripLengths", "filterValues": ["one_week"]},
        {"filterName": "itemsPerGrid", "filterValues": [str(STAYSSEARCH_PAGE_SIZE)]},
        {"filterName": "monthlyEndDate", "filterValues": ["2026-07-01"]},
        {"filterName": "monthlyLength", "filterValues": ["3"]},
        {"filterName": "monthlyStartDate", "filterValues": ["2026-04-01"]},
        {"filterName": "neLat", "filterValues": [f"{ne_lat:.15f}"]},
        {"filterName": "neLng", "filterValues": [f"{ne_lng:.15f}"]},
        {"filterName": "placeId", "filterValues": ["ChIJKcEGZna4lxIRwOzSAv-b67c"]},
        {"filterName": "priceFilterInputType", "filterValues": ["2"]},
        {"filterName": "priceFilterNumNights", "filterValues": ["5"]},
        {"filterName": "query", "filterValues": ["Mallorca, Spain"]},
        {"filterName": "refinementPaths", "filterValues": ["/homes"]},
        {"filterName": "screenSize", "filterValues": ["large"]},
        {"filterName": "searchByMap", "filterValues": ["true"]},
        {"filterName": "searchMode", "filterValues": ["regular_search"]},
        {"filterName": "swLat", "filterValues": [f"{sw_lat:.15f}"]},
        {"filterName": "swLng", "filterValues": [f"{sw_lng:.15f}"]},
        {"filterName": "tabId", "filterValues": ["home_tab"]},
        {"filterName": "version", "filterValues": ["1.8.8"]},
        {"filterName": "zoomLevel", "filterValues": ["11"]},
    ]

    stays_search_request = {
        "metadataOnly": False,
        "requestedPageType": "STAYS_SEARCH",
        "searchType": "user_map_move",
        "treatmentFlags": treatment_flags,
        "skipHydrationListingIds": [],
        "maxMapItems": 9999,
        "rawParams": raw_params_common,
    }

    stays_map_search_request_v2 = {
        "metadataOnly": False,
        "requestedPageType": "STAYS_SEARCH",
        "searchType": "user_map_move",
        "treatmentFlags": treatment_flags,
        "skipHydrationListingIds": [],
        "rawParams": [p for p in raw_params_common if p.get("filterName") != "itemsPerGrid"],
    }

    return {
        "operationName": "StaysSearch",
        "variables": {
            "staysSearchRequest": stays_search_request,
            "staysMapSearchRequestV2": stays_map_search_request_v2,
            "isLeanTreatment": False,
            "aiSearchEnabled": False,
            "skipExtendedSearchParams": False,
        },
        "extensions": {
            "persistedQuery": {
                "version": 1,
                "sha256Hash": STAYSSEARCH_HASH,
            }
        },
    }


def _extract_search_results(json_data: dict) -> list[dict]:
    """
    Extract searchResults list from StaysSearch JSON response.

    We try a couple of likely paths based on current Airbnb structure.
    """
    if not isinstance(json_data, dict):
        return []

    data = json_data.get("data") or {}
    pres = data.get("presentation") or {}
    stay_search = pres.get("staysSearch") or pres.get("staySearch") or {}
    results = stay_search.get("results") or {}
    search_results = results.get("searchResults")
    if isinstance(search_results, list):
        return search_results

    # Fallback: top-level searchResults
    sr = json_data.get("searchResults")
    if isinstance(sr, list):
        return sr
    return []


def _extract_listing_id_from_result(result: dict) -> str:
    """
    Extract listing ID from a single searchResults entry.
    """
    if not isinstance(result, dict):
        return ""
    # Prefer legacyId when present (numeric /rooms/<id>).
    legacy = None
    listing = result.get("listing")
    if isinstance(listing, dict):
        legacy = listing.get("legacyId")
    if isinstance(legacy, (str, int)) and str(legacy).isdigit():
        return str(legacy)

    # Common shapes seen in StaysSearch responses.
    for path in (
        ("demandStayListing", "id"),
        ("listing", "id"),
    ):
        node = result
        ok = True
        for key in path:
            if not isinstance(node, dict) or key not in node:
                ok = False
                break
            node = node[key]
        if ok and isinstance(node, (str, int)):
            val = str(node)
            if val.isdigit():
                return val
            # Sometimes Airbnb returns a base64-encoded global id like:
            # "RGVtYW5kU3RheUxpc3Rpbmc6MjM2NzQxMzI=" -> "DemandStayListing:23674132"
            try:
                padded = val + ("=" * (-len(val) % 4))
                decoded = base64.b64decode(padded).decode("utf-8", errors="ignore")
                m = re.search(r":(\d{3,})\b", decoded)
                if m:
                    return m.group(1)
            except Exception:
                pass
    return ""


def _split_bbox_quadtree(sw_lat: float, sw_lng: float, ne_lat: float, ne_lng: float):
    """
    Split a bbox into four child bboxes (quadtree).
    """
    mid_lat = (sw_lat + ne_lat) / 2.0
    mid_lng = (sw_lng + ne_lng) / 2.0
    return [
        (sw_lat, sw_lng, mid_lat, mid_lng),  # SW
        (sw_lat, mid_lng, mid_lat, ne_lng),  # SE
        (mid_lat, sw_lng, ne_lat, mid_lng),  # NW
        (mid_lat, mid_lng, ne_lat, ne_lng),  # NE
    ]


def _normalize_location(raw: str) -> str:
    """Prefer short 'Place, Spain' style; strip page titles and listing-type prefixes."""
    if not raw or "Airbnb" in raw or " - " in raw:
        return ""
    raw = raw.strip()
    # Strip listing-type prefix so we get "Alaró, Spain" from "Entire home in Alaró, Spain"
    prefixes = (
        "Entire rental unit in ",
        "Entire home in ",
        "Entire villa in ",
        "Entire townhouse in ",
        "Entire condo in ",
        "Entire cottage in ",
        "Entire apartment in ",
        "Entire chalet in ",
        "Entire cabin in ",
        "Private room in ",
        "Shared room in ",
        "Hotel room in ",
        "Room in ",
        "hotel in ",
        "boutique hotel in ",
        "bed and breakfast in ",
        "Bed and breakfast in ",
        "Apartment in ",
        "House in ",
    )
    for prefix in prefixes:
        if raw.lower().startswith(prefix.lower()) and len(raw) <= 70:
            raw = raw[len(prefix) :].strip()
            break
    # Accept if it looks like "Place, Spain" (or similar) and is a reasonable length
    if 3 <= len(raw) <= 60 and (", Spain" in raw or ", Balearic" in raw or ", Illes Balears" in raw):
        return raw
    return ""


def _response_text(response):
    """Get response body as text. Safe for Zyte httpResponseBody (raw/binary) responses where .text raises."""
    try:
        return response.text or ""
    except (AttributeError, NotSupported):
        pass
    body = getattr(response, "body", None)
    if body is None:
        return ""
    if isinstance(body, bytes):
        return body.decode("utf-8", errors="replace")
    return str(body)


def _extract_property_name(response) -> str:
    """Extract the property/listing name from Airbnb's embedded JSON or page title."""
    text = _response_text(response)

    for pattern in (
        re.compile(r'"name"\s*:\s*"([^"]{2,120})"'),
        re.compile(r'"title"\s*:\s*"([^"]{2,120})"'),
    ):
        for m in pattern.finditer(text):
            name = m.group(1).strip()
            if not name or "airbnb" in name.lower():
                continue
            if any(skip in name.lower() for skip in (
                "stayssearch", "operationname", "filtername",
                "searchmode", "flexibletriplengths", "screensize",
            )):
                continue
            try:
                name = json.loads(f'"{name}"')
            except Exception:
                pass
            if 2 <= len(name) <= 120:
                return name

    title_m = re.search(r"<title[^>]*>([^<]+)</title>", text, re.IGNORECASE)
    if title_m:
        title = title_m.group(1).strip()
        for suffix in (" - Airbnb", " | Airbnb", " · Airbnb"):
            if title.endswith(suffix):
                title = title[:-len(suffix)].strip()
        if 2 <= len(title) <= 120:
            return title

    return ""


def _extract_description_text(payload_text: str) -> str:
    """
    Extract the full listing description text from Airbnb's embedded JSON payload.
    We target the DESCRIPTION section htmlText, decode escape sequences, and convert <br> to newlines.
    """
    if not payload_text:
        return ""

    # Airbnb currently uses sectionId="DESCRIPTION_DEFAULT" for the main "About this space" block.
    # The value is a JSON string, so it is escaped in the HTML payload.
    section_idx = payload_text.find('"sectionId":"DESCRIPTION_DEFAULT"')
    if section_idx == -1:
        section_idx = payload_text.find('"sectionId":"DESCRIPTION"')
    if section_idx == -1:
        return ""

    html_key = '"htmlText":"'
    html_idx = payload_text.find(html_key, section_idx)
    if html_idx == -1:
        return ""

    # Parse the JSON string value safely (handle escaped quotes/backslashes) without relying on fragile regex.
    i = html_idx + len(html_key)
    raw_chars = []
    escaped = False
    while i < len(payload_text):
        ch = payload_text[i]
        if escaped:
            raw_chars.append(ch)
            escaped = False
        else:
            if ch == "\\":
                raw_chars.append(ch)
                escaped = True
            elif ch == '"':
                break
            else:
                raw_chars.append(ch)
        i += 1

    raw = "".join(raw_chars)
    # Decode JSON string escapes safely.
    try:
        decoded = json.loads(f'"{raw}"')
    except Exception:
        decoded = raw

    # Convert line breaks and strip tags.
    decoded = re.sub(r"<br\\s*/?>", "\n", decoded, flags=re.IGNORECASE)
    decoded = re.sub(r"<[^>]+>", "", decoded)
    return decoded.strip()


def _parse_lat_lng_strings(lat_str: str, lng_str: str):
    """
    Parse two numeric strings into validated latitude/longitude floats.
    Returns (lat, lng) or (None, None) if not numeric or out of range.
    """
    try:
        lat = float((lat_str or "").strip())
        lng = float((lng_str or "").strip())
    except (ValueError, TypeError):
        return None, None
    if not (-90.0 <= lat <= 90.0 and -180.0 <= lng <= 180.0):
        return None, None
    return lat, lng


# Listing map markers (e.g. Google Maps Platform) expose the pin as position="lat,lng".
_MAP_POSITION_ATTR_RE = re.compile(
    r'\bposition\s*=\s*["\']([^"\']+)["\']',
    re.IGNORECASE,
)

# Embedded PDP / JSON chunks: common key pairs for approximate listing coordinates.
# Tuple entries are (regex, swap_groups): swap True means group1 is lng and group2 is lat.
_JSON_LAT_LNG_PATTERNS = (
    (
        re.compile(
            r'"latitude"\s*:\s*(-?\d+(?:\.\d+)?)\s*,\s*"longitude"\s*:\s*(-?\d+(?:\.\d+)?)',
            re.IGNORECASE,
        ),
        False,
    ),
    (
        re.compile(
            r'"longitude"\s*:\s*(-?\d+(?:\.\d+)?)\s*,\s*"latitude"\s*:\s*(-?\d+(?:\.\d+)?)',
            re.IGNORECASE,
        ),
        True,
    ),
    (
        re.compile(
            r'"lat"\s*:\s*(-?\d+(?:\.\d+)?)\s*,\s*"lng"\s*:\s*(-?\d+(?:\.\d+)?)',
            re.IGNORECASE,
        ),
        False,
    ),
    (
        re.compile(
            r'"lng"\s*:\s*(-?\d+(?:\.\d+)?)\s*,\s*"lat"\s*:\s*(-?\d+(?:\.\d+)?)',
            re.IGNORECASE,
        ),
        True,
    ),
)


def _extract_coordinates(response):
    """
    Extract approximate listing coordinates from the room detail HTML.

    Extraction order (first valid pair wins):
    1) Map marker attributes — `position="lat,lng"` (e.g. gmp-advanced-marker). Airbnb pins the listing on
       the map with explicit coordinates; this is the most reliable signal tied to the map UI.
    2) Embedded JSON / script payloads — `"latitude"/"longitude"` or `"lat"/"lng"` pairs as they appear in
       minified PDP data (fallback when markers are absent or obfuscated).

    Why prefer coordinates over the human-readable `location` string: labels like "Palma, Spain" or
    "S'Estanyol, Illes Balears, Spain" are ambiguous for downstream municipality validation; lat/lng can be
    reverse-geocoded or checked against boundaries deterministically.

    Returns:
        (latitude, longitude) as floats when a valid pair is found, else (None, None).
    """
    text = _response_text(response)
    if not text:
        return None, None

    # 1) Map marker position="lat,lng" (comma-separated numbers; skip non-numeric junk).
    for m in _MAP_POSITION_ATTR_RE.finditer(text):
        raw = (m.group(1) or "").strip()
        parts = [p.strip() for p in raw.split(",") if p.strip()]
        if len(parts) != 2:
            continue
        lat, lng = _parse_lat_lng_strings(parts[0], parts[1])
        if lat is not None:
            return lat, lng

    # 2) JSON-like lat/lng pairs in page payload (first valid match per pattern, patterns in sensible order).
    for rx, swap in _JSON_LAT_LNG_PATTERNS:
        jm = rx.search(text)
        if not jm:
            continue
        a, b = jm.group(1), jm.group(2)
        if swap:
            lat, lng = _parse_lat_lng_strings(b, a)
        else:
            lat, lng = _parse_lat_lng_strings(a, b)
        if lat is not None:
            return lat, lng

    return None, None


def _extract_location(response) -> str:
    """Extract the location string shown on the listing page (e.g. 'Palma, Spain'), usually above the map."""
    text = _response_text(response)

    # 1) Try XPath: elements containing ", Spain" or ", Balearic Islands" / ", Illes Balears"
    for xpath in (
        "//a[contains(., ', Spain') or contains(., ', Balearic Islands') or contains(., ', Illes Balears')]/text()",
        "//span[contains(., ', Spain') or contains(., ', Balearic Islands') or contains(., ', Illes Balears')]/text()",
        "//*[contains(., ', Spain') or contains(., ', Balearic Islands') or contains(., ', Illes Balears')]/text()",
    ):
        parts = response.xpath(xpath).getall()
        for part in parts:
            part = (part or "").strip()
            if ", Spain" in part or ", Balearic" in part or ", Illes Balears" in part:
                out = _normalize_location(part)
                if out:
                    return out

    # 2) Regex on raw HTML: ">Place, Spain<" or ">Place, Balearic Islands<"
    for pattern in (LOCATION_PATTERN, LOCATION_ATTR_PATTERN):
        m = pattern.search(text)
        if m:
            loc = _normalize_location(m.group(1).strip())
            if loc:
                return loc

    # 3) Fallback: JSON-LD (Place or LocalBusiness with address in Spain)
    for script in response.xpath('//script[@type="application/ld+json"]//text()').getall():
        try:
            data = json.loads(script)
            addr = None
            if isinstance(data, dict) and data.get("address"):
                addr = data["address"]
            elif isinstance(data, list):
                for item in data:
                    if isinstance(item, dict) and item.get("address"):
                        addr = item["address"]
                        break
            if not addr or not isinstance(addr, dict):
                continue
            country = addr.get("addressCountry")
            if isinstance(country, dict):
                country = country.get("name") or ""
            country = str(country or "")
            if country and "Spain" not in country and "España" not in country:
                continue
            locality = addr.get("addressLocality") or addr.get("addressRegion") or ""
            if locality and 2 <= len(locality) <= 60:
                out = _normalize_location(f"{locality}, Spain")
                if out:
                    return out
        except (json.JSONDecodeError, TypeError):
            continue

    return ""


# Max guests: capacity in the listing overview row under the title (e.g. "6 guests"), not prose in
# the description (which may mention unrelated counts like "events for up to 50 guests").
MAX_GUESTS_PATTERN = re.compile(r"\b(\d+)\s*guest(?:s)?\b", re.IGNORECASE)

# Airbnb PDP renders the visible stats row inside a stable section id (guests, bedrooms, beds, baths).
_OVERVIEW_SECTION_IDS = ("OVERVIEW_DEFAULT_V2", "OVERVIEW_DEFAULT")

# When structured overview markup is missing, cut HTML before these markers so a regex fallback
# does not read the long-form description (where misleading "N guests" phrases often appear).
_MAX_GUESTS_FALLBACK_CUT_MARKERS = (
    'data-section-id="DESCRIPTION',
    "data-section-id='DESCRIPTION",
    'data-section-id="ABOUT_DEFAULT',
    "data-section-id='ABOUT_DEFAULT",
)

# Last-resort cap (chars) if no cut marker exists — still avoids scanning unbounded megabyte payloads.
_MAX_GUESTS_FALLBACK_HEAD_CHARS = 32000


def _max_guests_from_overview_dom(response) -> str:
    """
    Prefer the visible overview block near the title (OVERVIEW_DEFAULT_V2 / OVERVIEW_DEFAULT).

    Full-document regex is unsafe: the description JSON/HTML often appears before or after the
    overview in the raw text order, and phrases like "up to 50 guests" must not override the real
    capacity shown in the overview row.
    """
    for sid in _OVERVIEW_SECTION_IDS:
        section = response.css(f'[data-section-id="{sid}"]')
        if not section:
            continue
        for li in section.css("li"):
            combined = " ".join(
                t.strip() for t in li.xpath(".//text()").getall() if t and t.strip()
            )
            m = MAX_GUESTS_PATTERN.search(combined)
            if m:
                return m.group(1)
        scoped = " ".join(t.strip() for t in section.xpath(".//text()").getall() if t and t.strip())
        m = MAX_GUESTS_PATTERN.search(scoped)
        if m:
            return m.group(1)
    return ""


def _max_guests_fallback_limited_regex(response) -> str:
    """
    If DOM overview extraction failed, search a header-sized slice only — never the full document.

    Prefer text before DESCRIPTION / ABOUT sections; otherwise only the first _MAX_GUESTS_FALLBACK_HEAD_CHARS
    so description paragraphs are unlikely to dominate the match.
    """
    text = _response_text(response)
    if not text:
        return ""
    for marker in _MAX_GUESTS_FALLBACK_CUT_MARKERS:
        idx = text.find(marker)
        if idx != -1:
            text = text[:idx]
            break
    else:
        text = text[:_MAX_GUESTS_FALLBACK_HEAD_CHARS]
    m = MAX_GUESTS_PATTERN.search(text)
    return m.group(1) if m else ""


def _extract_max_guests(response) -> str:
    """Extract maximum number of guests from the listing overview. Returns empty string if not found."""
    out = _max_guests_from_overview_dom(response)
    if out:
        return out
    return _max_guests_fallback_limited_regex(response)


# Host overview lives in embedded PDP JSON as PdpHostOverviewDefaultSection (stable __typename).
_HOST_OVERVIEW_MARKER = "PdpHostOverviewDefaultSection"
_YEARS_HOSTING_RE = re.compile(r"^(\d+)\s+years?\s+hosting\s*$", re.IGNORECASE)
_NEW_HOST_RE = re.compile(r"^New Host\s*$", re.IGNORECASE)


def _extract_host_fields(payload_text: str) -> dict:
    """
    Extract host name, profile URL, years hosting, and superhost flag from Airbnb's embedded JSON.

    The listing HTML includes a PdpHostOverviewDefaultSection with title "Hosted by …",
    overviewItems (Superhost, "N years hosting", "New Host"), and hostId in logging eventData.
    """
    out = {
        "host_name": "",
        "host_url": "",
        "host_years_hosting": None,
        "host_is_superhost": False,
    }
    if not payload_text:
        return out

    start = payload_text.find(_HOST_OVERVIEW_MARKER)
    if start == -1:
        return out

    chunk = payload_text[start : start + 4500]

    hosted_m = re.search(r'"title":"Hosted by ([^"]+)"', chunk)
    if hosted_m:
        out["host_name"] = hosted_m.group(1).strip()

    host_id_m = re.search(r'"hostId":"(\d+)"', chunk)
    if host_id_m:
        out["host_url"] = f"https://www.airbnb.com/users/show/{host_id_m.group(1)}"

    super_m = re.search(r'"isSuperHost":"(true|false)"', chunk)
    if super_m and super_m.group(1) == "true":
        out["host_is_superhost"] = True
    if '"badge":"SUPER_HOST"' in chunk:
        out["host_is_superhost"] = True

    ov_start = chunk.find('"overviewItems"')
    ha_start = chunk.find('"hostAvatar"', ov_start if ov_start != -1 else 0)
    if ov_start != -1 and ha_start != -1 and ha_start > ov_start:
        items_region = chunk[ov_start:ha_start]
        years_set = False
        for t_m in re.finditer(r'"title":"([^"]*)"', items_region):
            title = t_m.group(1).strip()
            if not title:
                continue
            if "superhost" in title.lower():
                out["host_is_superhost"] = True
            if _NEW_HOST_RE.match(title):
                out["host_years_hosting"] = 0
                years_set = True
            else:
                ym = _YEARS_HOSTING_RE.match(title)
                if ym:
                    out["host_years_hosting"] = int(ym.group(1))
                    years_set = True
        if not years_set:
            out["host_years_hosting"] = None

    return out


# Listing aggregate rating in embedded PDP JSON (one main value per page in practice).
_GUEST_SATISFACTION_JSON_RE = re.compile(
    r'"guestSatisfactionOverall"\s*:\s*(null|\d+(?:\.\d+)?)'
)
_REVIEW_COUNT_JSON_RE = re.compile(r'"reviewCount"\s*:\s*(\d+)')
_RATED_STARS_HTML_RE = re.compile(
    r"Rated\s+([\d.]+)\s+out of 5 stars", re.IGNORECASE
)
# "5 reviews" / "33 reviews" in the reviews CTA (data-button-content span)
_REVIEWS_SPAN_HTML_RE = re.compile(
    r'data-button-content="true"[^>]*>\s*(\d+)\s+reviews\s*<', re.IGNORECASE
)


def _extract_rating_and_reviews(payload_text: str) -> dict:
    """
    Extract aggregate star rating and review count from PDP JSON, with HTML fallback.

    New listings use reviewCount 0 and guestSatisfactionOverall null — both fields are
    left unset (None) so feeds show blank/null, per product copy ("New listing").
    """
    out: dict = {"rating": None, "review_count": None}
    if not payload_text:
        return out

    rc_m = _REVIEW_COUNT_JSON_RE.search(payload_text)
    review_count = int(rc_m.group(1)) if rc_m else None

    gso_m = _GUEST_SATISFACTION_JSON_RE.search(payload_text)
    gso_raw = gso_m.group(1) if gso_m else None

    if review_count is not None and review_count == 0:
        return out

    rating_val: float | None = None
    if gso_raw and gso_raw != "null":
        rating_val = float(gso_raw)

    if review_count is not None and review_count > 0:
        if rating_val is None:
            hm = _RATED_STARS_HTML_RE.search(payload_text)
            if hm:
                rating_val = float(hm.group(1))
        if rating_val is not None:
            out["rating"] = rating_val
            out["review_count"] = review_count
            return out

    # JSON review count missing: try visible "Rated X …" + "N reviews" in HTML
    hm = _RATED_STARS_HTML_RE.search(payload_text)
    rm = _REVIEWS_SPAN_HTML_RE.search(payload_text)
    if hm and rm:
        c = int(rm.group(1))
        if c > 0:
            out["rating"] = float(hm.group(1))
            out["review_count"] = c

    return out


def _listing_key(url: str) -> str:
    """Normalize listing URL to a stable key for deduplication (one request per listing)."""
    base = url.split("?")[0].strip().rstrip("/")
    if "/rooms/" in base:
        parts = base.split("/rooms/")[-1].split("/")
        if parts and parts[0].strip():
            return parts[0].strip()
    return base


def _is_listing_url(url: str) -> bool:
    """True if URL looks like a listing detail page (numeric id), not /rooms/plus or /rooms/experiences."""
    key = _listing_key(url)
    return key.isdigit() if key else False


class AirbnbMallorcaSpider(scrapy.Spider):
    name = "airbnb_mallorca"
    # Include country TLDs so listing links (e.g. www.airbnb.ie) are not dropped by OffsiteMiddleware.
    allowed_domains = [
        "www.airbnb.com", "www.airbnb.co.uk", "www.airbnb.es", "www.airbnb.ie",
        "airbnb.com", "airbnb.co.uk", "airbnb.es", "airbnb.ie",
    ]

    # Max speed: previous job had 0 errors at 20 concurrency; increased for faster crawl. If you see 429s, lower TARGET_CONCURRENCY.
    custom_settings = {
        "CONCURRENT_REQUESTS": 64,
        "CONCURRENT_REQUESTS_PER_DOMAIN": 48,
        "ROBOTSTXT_OBEY": False,
        "AUTOTHROTTLE_ENABLED": True,
        "AUTOTHROTTLE_TARGET_CONCURRENCY": 48,
        "AUTOTHROTTLE_MAX_CONCURRENCY": 64,
        "AUTOTHROTTLE_START_DELAY": 0.1,
        "AUTOTHROTTLE_DEBUG": False,
    }

    # Safety valve: cap quadtree recursion depth. You can override at runtime:
    #   scrapy crawl airbnb_mallorca -a max_depth=12
    max_depth = 12

    def start_requests(self):
        """
        Entry point: start from the full Mallorca bbox and drive discovery via
        StaysSearch JSON + quadtree (18 => split, <18 => leaf, no pagination).
        """
        self._seen_listing_keys = set()

        if STAYSSEARCH_HASH == "REPLACE_WITH_PERSISTED_QUERY_HASH":
            self.logger.error(
                "STAYSSEARCH_HASH still has the placeholder value. "
                "If discovery starts failing with 400 errors, grab the current "
                "StaysSearch URL from your browser DevTools and paste the hash "
                "into STAYSSEARCH_HASH in airbnb_mallorca.py."
            )

        zyte_list_meta = {"httpResponseBody": True}
        root_bbox = (MALLORCA_SW_LAT, MALLORCA_SW_LNG, MALLORCA_NE_LAT, MALLORCA_NE_LNG)
        payload = _build_stayssearch_payload(*root_bbox)
        yield scrapy.Request(
            _stayssearch_url(),
            method="POST",
            body=json.dumps(payload),
            headers={
                "Content-Type": "application/json",
                "x-airbnb-api-key": AIRBNB_WEB_API_KEY,
                "x-airbnb-graphql-platform": "web",
                "x-airbnb-supports-airlock-v2": "true",
            },
            dont_filter=True,
            callback=self.parse_stayssearch_node,
            errback=self.handle_list_error,
            meta={
                "zyte_api_automap": zyte_list_meta,
                "bbox": root_bbox,
                "depth": 0,
                "dont_merge_cookies": True,
            },
        )

    def parse_stayssearch_node(self, response):
        """
        Handle a single StaysSearch JSON response for one bbox node.

        Rule:
        - len(searchResults) == 18 -> split bbox into 4 and recurse.
        - len(searchResults) < 18  -> treat as leaf; schedule detail pages, no pagination.
        """
        bbox = response.meta.get("bbox")
        depth = int(response.meta.get("depth", 0) or 0)

        if response.status != 200:
            self.logger.warning(
                "StaysSearch node failed with status %s for bbox=%s at depth=%s",
                response.status,
                bbox,
                depth,
            )
            return

        try:
            data = json.loads(_response_text(response))
        except json.JSONDecodeError:
            self.logger.warning("Failed to decode StaysSearch JSON for bbox=%s depth=%s", bbox, depth)
            return

        search_results = _extract_search_results(data)
        count = len(search_results)
        leaf = count < STAYSSEARCH_PAGE_SIZE

        self.logger.info(
            "StaysSearch bbox=%s depth=%s results=%s leaf=%s",
            bbox,
            depth,
            count,
            leaf,
        )
        if count == 0:
            # High-signal debug: when payload is accepted (200) but returns no results,
            # log a compact view of the response so we can align to the correct JSON path.
            top_keys = list(data.keys()) if isinstance(data, dict) else []
            self.logger.warning(
                "StaysSearch returned 0 results for bbox=%s depth=%s. top_keys=%s body_snippet=%r",
                bbox,
                depth,
                top_keys,
                (_response_text(response) or "")[:500],
            )

        zyte_detail = {"httpResponseBody": True}

        if leaf:
            # Leaf node: schedule detail pages for all unique listing IDs.
            for result in search_results:
                listing_id = _extract_listing_id_from_result(result)
                if not listing_id:
                    continue
                url = f"https://www.airbnb.com/rooms/{listing_id}"
                key = _listing_key(url)
                if key in self._seen_listing_keys:
                    continue
                self._seen_listing_keys.add(key)
                yield scrapy.Request(
                    url,
                    callback=self.parse_detail,
                    errback=self.handle_detail_error,
                    dont_filter=True,
                    meta={
                        "zyte_api": zyte_detail,
                        "municipality": "Mallorca",
                    },
                )
            return

        # Internal node: split bbox and recurse (no pagination).
        max_depth = int(getattr(self, "max_depth", 12) or 12)
        if depth >= max_depth:
            # Depth cap reached: treat as leaf to ensure we still collect listings.
            for result in search_results:
                listing_id = _extract_listing_id_from_result(result)
                if not listing_id:
                    continue
                url = f"https://www.airbnb.com/rooms/{listing_id}"
                key = _listing_key(url)
                if key in self._seen_listing_keys:
                    continue
                self._seen_listing_keys.add(key)
                yield scrapy.Request(
                    url,
                    callback=self.parse_detail,
                    errback=self.handle_detail_error,
                    dont_filter=True,
                    meta={
                        "zyte_api": zyte_detail,
                        "municipality": "Mallorca",
                    },
                )
            return

        if not bbox or len(bbox) != 4:
            return
        sw_lat, sw_lng, ne_lat, ne_lng = bbox
        if (ne_lat - sw_lat) < MIN_CELL_LAT_SPAN or (ne_lng - sw_lng) < MIN_CELL_LNG_SPAN:
            # Box is already very small; treat it as leaf even if capped.
            for result in search_results:
                listing_id = _extract_listing_id_from_result(result)
                if not listing_id:
                    continue
                url = f"https://www.airbnb.com/rooms/{listing_id}"
                key = _listing_key(url)
                if key in self._seen_listing_keys:
                    continue
                self._seen_listing_keys.add(key)
                yield scrapy.Request(
                    url,
                    callback=self.parse_detail,
                    errback=self.handle_detail_error,
                    dont_filter=True,
                    meta={
                        "zyte_api": zyte_detail,
                        "municipality": "Mallorca",
                    },
                )
            return

        children = _split_bbox_quadtree(sw_lat, sw_lng, ne_lat, ne_lng)
        zyte_list_meta = {"httpResponseBody": True}
        for child_bbox in children:
            payload = _build_stayssearch_payload(*child_bbox)
            yield scrapy.Request(
                _stayssearch_url(),
                method="POST",
                body=json.dumps(payload),
                headers={
                    "Content-Type": "application/json",
                    "x-airbnb-api-key": AIRBNB_WEB_API_KEY,
                    "x-airbnb-graphql-platform": "web",
                    "x-airbnb-supports-airlock-v2": "true",
                },
                dont_filter=True,
                callback=self.parse_stayssearch_node,
                errback=self.handle_list_error,
                meta={
                    "zyte_api_automap": zyte_list_meta,
                    "bbox": child_bbox,
                    "depth": depth + 1,
                    "dont_merge_cookies": True,
                },
            )

    def handle_list_error(self, failure):
        """Log failed list/discovery requests for re-run or debugging."""
        request = getattr(failure, "request", None)
        url = request.url if request else "unknown"
        self.logger.error(
            "List request failed: url=%s municipality=%s reason=%s",
            url,
            request.meta.get("municipality", "") if request else "",
            failure.getTraceback(),
        )

    def handle_detail_error(self, failure):
        """Log failed detail requests so URLs can be re-tried or inspected."""
        request = getattr(failure, "request", None)
        url = request.url if request else "unknown"
        self.logger.error(
            "Detail request failed: url=%s municipality=%s reason=%s",
            url,
            request.meta.get("municipality", "") if request else "",
            failure.getTraceback(),
        )

    def closed(self, reason):
        """Log extraction summary and unique listing count at end of crawl."""
        unique_listings = len(getattr(self, "_seen_listing_keys", set()))
        self.logger.info(
            "Airbnb Mallorca crawl finished: %s unique listing IDs requested",
            unique_listings,
        )
        if not getattr(self, "crawler", None) or not self.crawler.stats:
            return
        with_reg = self.crawler.stats.get_value("airbnb_mallorca/items_with_registration") or 0
        without_reg = self.crawler.stats.get_value("airbnb_mallorca/items_without_registration") or 0
        total = with_reg + without_reg
        if total:
            pct = 100.0 * with_reg / total
            self.logger.info(
                "Airbnb Mallorca extraction summary: %s items with registration number, %s without (%.1f%% with reg)",
                with_reg,
                without_reg,
                pct,
            )

    def parse_detail(self, response):
        # Only process successful responses; failed ones are retried by Scrapy
        if response.status != 200:
            self.logger.warning(
                "Detail page %s returned status %s (municipality=%s), skipping",
                response.url,
                response.status,
                response.meta.get("municipality", ""),
            )
            return

        text = _response_text(response)
        description_text = _extract_description_text(text)
        registration_number = extract_registration_number(text, description_text) or ""

        # Stats for extraction rate (see summary at end of crawl)
        if self.crawler.stats:
            if registration_number:
                self.crawler.stats.inc_value("airbnb_mallorca/items_with_registration")
            else:
                self.crawler.stats.inc_value("airbnb_mallorca/items_without_registration")
                self.logger.debug(
                    "No registration number on detail page (listing may have none or text not in response): %s",
                    response.url,
                )

        # Listing ID from URL for stable reference (same logic as dedup key)
        listing_id = _listing_key(response.url) if "/rooms/" in response.url else ""

        # Zyte httpResponseBody returns a response that is not text-like; .xpath() raises NotSupported.
        # Build an HtmlResponse from decoded body so location / max_guests / coordinates use the DOM.
        html_response = HtmlResponse(url=response.url, body=text.encode("utf-8"), encoding="utf-8")
        location = _extract_location(html_response)
        # Approximate map coordinates when present (preferred over `location` for boundary/municipality checks).
        latitude, longitude = _extract_coordinates(html_response)
        max_guests = _extract_max_guests(html_response)
        property_name = _extract_property_name(html_response)
        picture_url = extract_picture_url(html_response, text)
        host_fields = _extract_host_fields(text)
        rating_fields = _extract_rating_and_reviews(text)

        item = AirbnbListingItem(
            url=response.url,
            location=location,
            latitude=latitude,
            longitude=longitude,
            registration_number=registration_number,
            description_text=description_text,
            listing_id=listing_id,
            max_guests=max_guests,
            property_name=property_name,
            picture_url=picture_url,
            host_name=host_fields["host_name"],
            host_url=host_fields["host_url"],
            host_years_hosting=host_fields["host_years_hosting"],
            host_is_superhost=host_fields["host_is_superhost"],
            rating=rating_fields["rating"],
            review_count=rating_fields["review_count"],
        )
        yield item
