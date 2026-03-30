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
from radarlicencias.spiders.airbnb_mallorca import (
    AirbnbMallorcaSpider,
    _extract_host_fields,
    _extract_rating_and_reviews,
    _is_listing_url,
    _listing_key,
    _normalize_location,
)


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


# Snippets from real PDP embedded JSON (PdpHostOverviewDefaultSection), anonymized IDs kept as in samples.
_LISA_HOST_SNIPPET = (
    'PdpHostOverviewDefaultSection","title":"Hosted by Lisa","overviewItems":'
    '[{"__typename":"PdpSbuiBasicListItem","title":"Superhost"},'
    '{"__typename":"PdpSbuiBasicListItem","title":"9 years hosting"}],'
    '"hostAvatar":{"__typename":"Avatar","badge":"SUPER_HOST",'
    '"loggingEventData":{"eventData":{"pdpContext":{"isSuperHost":"true","hostId":"134859446"}}}}'
)

_PRIORITY_HOST_SNIPPET = (
    'PdpHostOverviewDefaultSection","title":"Hosted by Priority Villas","overviewItems":'
    '[{"__typename":"PdpSbuiBasicListItem","title":"9 years hosting"}],'
    '"hostAvatar":{"__typename":"Avatar","badge":null,'
    '"loggingEventData":{"eventData":{"pdpContext":{"isSuperHost":"false","hostId":"149209395"}}}}'
)

_ATALAYA_HOST_SNIPPET = (
    'PdpHostOverviewDefaultSection","title":"Hosted by Atalaya","overviewItems":'
    '[{"__typename":"PdpSbuiBasicListItem","title":"New Host"}],'
    '"hostAvatar":{"__typename":"Avatar","badge":null,'
    '"loggingEventData":{"eventData":{"pdpContext":{"isSuperHost":"false","hostId":"750459928"}}}}'
)


class TestExtractHostFields(unittest.TestCase):
    def test_lisa_superhost_nine_years(self):
        h = _extract_host_fields(_LISA_HOST_SNIPPET)
        self.assertEqual(h["host_name"], "Lisa")
        self.assertEqual(h["host_url"], "https://www.airbnb.com/users/show/134859446")
        self.assertEqual(h["host_years_hosting"], 9)
        self.assertTrue(h["host_is_superhost"])

    def test_priority_villas_nine_years_not_superhost(self):
        h = _extract_host_fields(_PRIORITY_HOST_SNIPPET)
        self.assertEqual(h["host_name"], "Priority Villas")
        self.assertEqual(h["host_url"], "https://www.airbnb.com/users/show/149209395")
        self.assertEqual(h["host_years_hosting"], 9)
        self.assertFalse(h["host_is_superhost"])

    def test_atalaya_new_host(self):
        h = _extract_host_fields(_ATALAYA_HOST_SNIPPET)
        self.assertEqual(h["host_name"], "Atalaya")
        self.assertEqual(h["host_url"], "https://www.airbnb.com/users/show/750459928")
        self.assertEqual(h["host_years_hosting"], 0)
        self.assertFalse(h["host_is_superhost"])

    def test_superhost_detected_from_title_only(self):
        text = (
            'PdpHostOverviewDefaultSection","title":"Hosted by Pat","overviewItems":'
            '[{"title":"superhost"},{"title":"3 years hosting"}],'
            '"hostAvatar":{"eventData":{"pdpContext":{"isSuperHost":"false","hostId":"1"}}}}'
        )
        h = _extract_host_fields(text)
        self.assertTrue(h["host_is_superhost"])

    def test_empty_when_no_section(self):
        self.assertEqual(_extract_host_fields("")["host_name"], "")
        self.assertEqual(_extract_host_fields("<html></html>")["host_url"], "")


class TestExtractRatingAndReviews(unittest.TestCase):
    def test_from_json_five_and_five(self):
        text = '"guestSatisfactionOverall":5,"reviewCount":5'
        r = _extract_rating_and_reviews(text)
        self.assertEqual(r["rating"], 5.0)
        self.assertEqual(r["review_count"], 5)

    def test_from_json_decimal_reviews(self):
        text = '"guestSatisfactionOverall":4.94,"reviewCount":33'
        r = _extract_rating_and_reviews(text)
        self.assertEqual(r["rating"], 4.94)
        self.assertEqual(r["review_count"], 33)

    def test_new_listing_null_and_zero(self):
        text = '"guestSatisfactionOverall":null,"reviewCount":0'
        r = _extract_rating_and_reviews(text)
        self.assertIsNone(r["rating"])
        self.assertIsNone(r["review_count"])

    def test_html_fallback(self):
        text = (
            '<span class="a8jt5op">Rated 4.5 out of 5 stars.</span>'
            '<span data-button-content="true" class="x">10 reviews</span>'
        )
        r = _extract_rating_and_reviews(text)
        self.assertEqual(r["rating"], 4.5)
        self.assertEqual(r["review_count"], 10)


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
