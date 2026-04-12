"""Tests for Mallorca registration extraction and provenance (license.py)."""

import unittest

from radarlicencias.extractors.license import (
    REGISTRATION_SOURCE_DESCRIPTION_STANDALONE,
    REGISTRATION_SOURCE_MALLORCA_REGIONAL_LABEL,
    REGISTRATION_SOURCE_NONE,
    REGISTRATION_SOURCE_SPAIN_NATIONAL_DERIVED,
    extract_registration_number_with_source,
)


class TestRegistrationProvenance(unittest.TestCase):
    def test_mallorca_regional_label_etv(self):
        text = """
        Registration Details
        Mallorca - Regional registration number
        ETV/11867
        """
        reg, src = extract_registration_number_with_source(text, "")
        self.assertEqual(reg, "ETV/11867")
        self.assertEqual(src, REGISTRATION_SOURCE_MALLORCA_REGIONAL_LABEL)

    def test_event_text_and_regional_block_prefers_regional(self):
        """Description mentions large guest counts; authoritative block still wins."""
        page = """
        Perfect for events up to 500 guests.
        Mallorca - Regional registration number
        ETV/99999
        """
        desc = "We also host weddings for 200 guests."
        reg, src = extract_registration_number_with_source(page, desc)
        self.assertEqual(reg, "ETV/99999")
        self.assertEqual(src, REGISTRATION_SOURCE_MALLORCA_REGIONAL_LABEL)

    def test_spain_national_derives_license(self):
        national = (
            "Some header\n"
            "ESFCTU12345678901234567890123456789012ETV/118671\n"
        )
        reg, src = extract_registration_number_with_source(national, "")
        self.assertEqual(reg, "ETV/11867")
        self.assertEqual(src, REGISTRATION_SOURCE_SPAIN_NATIONAL_DERIVED)

    def test_standalone_etv_in_description(self):
        page = "<html><body>No regional block here.</body></html>"
        desc = "Nice place. ETV/555 in the text."
        reg, src = extract_registration_number_with_source(page, desc)
        self.assertEqual(reg, "ETV/555")
        self.assertEqual(src, REGISTRATION_SOURCE_DESCRIPTION_STANDALONE)

    def test_false_positive_avoided_inside_national_string(self):
        """Standalone ETV inside the long national blob must not win via strategy 2."""
        blob = (
            "ESFCTU11111111111111111111111111111111ETV/777771\n"
            "Mallorca - Regional registration number\n"
            "ETV/11867\n"
        )
        reg, src = extract_registration_number_with_source(blob, "")
        self.assertEqual(reg, "ETV/11867")
        self.assertEqual(src, REGISTRATION_SOURCE_MALLORCA_REGIONAL_LABEL)

    def test_none_when_missing(self):
        reg, src = extract_registration_number_with_source("hello world", "")
        self.assertEqual(reg, "")
        self.assertEqual(src, REGISTRATION_SOURCE_NONE)


if __name__ == "__main__":
    unittest.main()
