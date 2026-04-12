# Radarlicencias crawlers - Item definitions
# Define fields once you share the exact data you need from each site.

import scrapy


class MallorcaLicenseItem(scrapy.Item):
    """Tourist license from Consell de Mallorca cens. List row + optional ficha (detail) fields."""

    signature = scrapy.Field()           # Signatura (license ref)
    commercial_name = scrapy.Field()     # Denominació comercial
    municipality = scrapy.Field()        # Municipi
    address = scrapy.Field()
    ficha_url = scrapy.Field()           # URL of "Ver ficha" / "Veu fitxa" detail page

    # From ficha (detail) page
    current_status = scrapy.Field()       # Estado actual (e.g. Activo, Baja)
    number_of_units = scrapy.Field()      # Número de unidades
    number_of_places = scrapy.Field()     # Número de plazas / Número de Plazas
    activity_start_date = scrapy.Field()  # Inicio de actividad / Desde (Entidades relacionadas)
    locality = scrapy.Field()             # Localidad (e.g. Port De Pollença)
    group = scrapy.Field()                # Grup (e.g. Estancia turística en vivienda)
    related_entity_name = scrapy.Field()  # Entidades relacionadas: Nombre (e.g. POLLENSA ESPAIS, SL.)
    related_entity_relation = scrapy.Field()  # Entidades relacionadas: Relación (e.g. Explotador)


class AirbnbListingItem(scrapy.Item):
    """Airbnb listing in Mallorca. Core fields for matching with Consell licenses."""

    # Core fields for matching
    url = scrapy.Field()  # Listing page URL
    location = scrapy.Field()  # Location shown on the listing page (e.g. "Palma, Spain"), usually above the map
    # Approximate listing map coordinates when present in HTML (preferred over location text for municipality checks).
    latitude = scrapy.Field()  # float or None
    longitude = scrapy.Field()  # float or None
    registration_number = scrapy.Field()  # Mallorca Regional Registration Number (ETV/...) from expanded description
    description_text = scrapy.Field()  # Full listing description text (for audit/validation of extracted license)
    property_name = scrapy.Field()  # Listing title/name (e.g. "Cozy Apartment in Palma")
    picture_url = scrapy.Field()  # URL of the main listing photo

    # Host (from HOST_OVERVIEW / PdpHostOverviewDefaultSection in embedded JSON)
    host_name = scrapy.Field()  # Display name only, without "Hosted by " prefix
    host_url = scrapy.Field()  # Public host profile URL (e.g. /users/show/<id>)
    host_years_hosting = scrapy.Field()  # int: years from "N years hosting"; 0 for "New Host"; empty if unknown
    host_is_superhost = scrapy.Field()  # bool

    # Guest-visible rating summary (embedded JSON; HTML fallback). None/null in feeds when new listing / no reviews.
    rating = scrapy.Field()  # float, e.g. 4.94 or 5.0
    review_count = scrapy.Field()  # int

    # Optional / housekeeping
    listing_id = scrapy.Field()  # From URL or page (e.g. rooms/12345)
    max_guests = scrapy.Field()  # Maximum number of guests allowed (shown under listing name)
