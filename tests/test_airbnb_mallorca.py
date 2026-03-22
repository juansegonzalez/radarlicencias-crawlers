# Offline tests for Airbnb Mallorca spider: helpers, extractors, and item construction.
# Run from project root: python -m pytest tests/test_airbnb_mallorca.py -v
# Or: python tests/test_airbnb_mallorca.py

import json
import os
import sys
import unittest

# Project root on path so radarlicencias is importable
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import scrapy
from scrapy.http import HtmlResponse

from radarlicencias.extractors.license import (
    extract_registration_number,
    normalize_registration,
)
from radarlicencias.spiders.airbnb_mallorca import AirbnbMallorcaSpider, _is_listing_url, _listing_key, _normalize_location


class TestListingKey(unittest.TestCase):
    def test_listing_key_from_rooms_url(self):
        self.assertEqual(_listing_key("https://www.airbnb.com/rooms/12345"), "12345")
        self.assertEqual(_listing_key("https://www.airbnb.es/rooms/98765?foo=bar"), "98765")
        self.assertEqual(_listing_key("https://www.airbnb.co.uk/rooms/111"), "111")

    def test_listing_key_non_listing(self):
        self.assertEqual(_listing_key("https://www.airbnb.com/rooms/plus"), "plus")
        self.assertEqual(_listing_key("https://www.airbnb.com/rooms/experiences/123"), "experiences")

    def test_is_listing_url(self):
        self.assertTrue(_is_listing_url("https://www.airbnb.com/rooms/12345"))
        self.assertTrue(_is_listing_url("https://www.airbnb.com/rooms/1"))
        self.assertFalse(_is_listing_url("https://www.airbnb.com/rooms/plus"))
        self.assertFalse(_is_listing_url("https://www.airbnb.com/rooms/experiences/123"))
        self.assertFalse(_is_listing_url("https://www.airbnb.com/s/Spain/homes"))


class TestNormalizeLocation(unittest.TestCase):
    def test_accepts_place_spain(self):
        self.assertEqual(_normalize_location("Palma, Spain"), "Palma, Spain")
        self.assertEqual(_normalize_location("Alaró, Spain"), "Alaró, Spain")

    def test_strips_listing_prefix(self):
        self.assertEqual(_normalize_location("Entire home in Palma, Spain"), "Palma, Spain")
        self.assertEqual(_normalize_location("Entire rental unit in Sóller, Spain"), "Sóller, Spain")
        self.assertEqual(_normalize_location("Private room in Sóller, Spain"), "Sóller, Spain")

    def test_rejects_empty_or_no_spain(self):
        self.assertEqual(_normalize_location(""), "")
        self.assertEqual(_normalize_location("Paris, France"), "")
        self.assertEqual(_normalize_location("Palma - Airbnb"), "")


class TestLicenseExtractor(unittest.TestCase):
    def test_extract_mallorca_regional(self):
        text = "Mallorca - Regional registration number:\\nETV/12345"
        self.assertEqual(extract_registration_number(text), "ETV/12345")

    def test_extract_mallorca_dash(self):
        text = "Mallorca - Regional registration number:\nETV-67890"
        self.assertEqual(extract_registration_number(text), "ETV/67890")

    def test_extract_generic_pattern(self):
        # Many listings (including non-ETV prefixes) still present the "Mallorca - Regional registration number" label.
        text = "Mallorca - Regional registration number:\\nTI/999\\nother"
        self.assertEqual(extract_registration_number(text), "TI/999")

    def test_extract_empty(self):
        self.assertEqual(extract_registration_number(""), "")
        self.assertEqual(extract_registration_number("No license here"), "")

    def test_normalize_registration(self):
        self.assertEqual(normalize_registration("ETV/12345"), "ETV/12345")
        self.assertEqual(normalize_registration("ETV-12345"), "ETV/12345")
        self.assertEqual(normalize_registration("CT 456"), "CT/456")
        self.assertEqual(normalize_registration("  ETV60/789  "), "ETV60/789")
        self.assertEqual(normalize_registration("ETV123"), "ETV/123")


if __name__ == "__main__":
    unittest.main()
