# Extractors for spiders: license patterns, registration number, etc.
from .license import (
    get_license_code,
    extract_registration_number,
    extract_registration_number_with_source,
    normalize_registration,
    REGISTRATION_SOURCE_DESCRIPTION_STANDALONE,
    REGISTRATION_SOURCE_MALLORCA_REGIONAL_LABEL,
    REGISTRATION_SOURCE_NONE,
    REGISTRATION_SOURCE_SPAIN_NATIONAL_DERIVED,
)

__all__ = [
    "get_license_code",
    "extract_registration_number",
    "extract_registration_number_with_source",
    "normalize_registration",
    "REGISTRATION_SOURCE_DESCRIPTION_STANDALONE",
    "REGISTRATION_SOURCE_MALLORCA_REGIONAL_LABEL",
    "REGISTRATION_SOURCE_NONE",
    "REGISTRATION_SOURCE_SPAIN_NATIONAL_DERIVED",
]
