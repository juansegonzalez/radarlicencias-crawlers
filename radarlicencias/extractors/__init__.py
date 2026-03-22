# Extractors for spiders: license patterns, registration number, etc.
from .license import (
    get_license_code,
    extract_registration_number,
    normalize_registration,
)

__all__ = ["get_license_code", "extract_registration_number", "normalize_registration"]
