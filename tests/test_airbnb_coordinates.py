"""Tests for Airbnb listing coordinate extraction from room detail HTML."""

import unittest

from scrapy.http import HtmlResponse

from radarlicencias.spiders.airbnb_mallorca import _extract_coordinates


def _html_response(body: str) -> HtmlResponse:
    return HtmlResponse(
        url="https://www.airbnb.com/rooms/12345",
        body=body.encode("utf-8"),
        encoding="utf-8",
    )


class TestAirbnbCoordinateExtraction(unittest.TestCase):
    def test_position_attribute_on_map_marker(self):
        body = """
        <gmp-advanced-marker position="39.7318,3.2613" title="Listing"></gmp-advanced-marker>
        """
        lat, lng = _extract_coordinates(_html_response(body))
        self.assertAlmostEqual(lat, 39.7318, places=6)
        self.assertAlmostEqual(lng, 3.2613, places=6)

    def test_no_coordinates_returns_none(self):
        body = """
        <html><body><span>Palma, Spain</span></body></html>
        """
        lat, lng = _extract_coordinates(_html_response(body))
        self.assertIsNone(lat)
        self.assertIsNone(lng)

    def test_malformed_position_skipped_until_valid_or_exhausted(self):
        body = """
        <div position="not-a-number,3.0"></div>
        <div position="91.0,3.0"></div>
        """
        lat, lng = _extract_coordinates(_html_response(body))
        self.assertIsNone(lat)
        self.assertIsNone(lng)

    def test_later_valid_position_after_malformed(self):
        body = """
        <div position="foo,bar"></div>
        <gmp-advanced-marker position="39.7318,3.2613"></gmp-advanced-marker>
        """
        lat, lng = _extract_coordinates(_html_response(body))
        self.assertAlmostEqual(lat, 39.7318, places=6)
        self.assertAlmostEqual(lng, 3.2613, places=6)

    def test_json_lat_lng_fallback(self):
        body = """
        <script>window.__PAYLOAD__={"lat":39.5,"lng":2.8};</script>
        """
        lat, lng = _extract_coordinates(_html_response(body))
        self.assertAlmostEqual(lat, 39.5)
        self.assertAlmostEqual(lng, 2.8)


if __name__ == "__main__":
    unittest.main()
