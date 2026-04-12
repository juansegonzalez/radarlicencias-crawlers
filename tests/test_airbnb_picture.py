"""Tests for Airbnb listing main photo extraction (hero DOM + tightened JSON fallback)."""

import json
import unittest

from scrapy.http import HtmlResponse

from radarlicencias.extractors.airbnb_picture import (
    BANNED_PICTURE_URL_SUBSTRINGS,
    extract_picture_url,
    is_banned_picture_url,
    _extract_picture_url_from_hero_html,
    _extract_picture_url_from_payload,
    _extract_picture_url_from_page_original_uri,
)


def _html_response(body: str) -> HtmlResponse:
    return HtmlResponse(
        url="https://www.airbnb.com/rooms/12345",
        body=body.encode("utf-8"),
        encoding="utf-8",
    )


GOOD_HERO_URI = (
    "https://a0.muscache.com/im/pictures/hosting/Hosting-1416895339858528728/"
    "original/43829f19-e78d-4c87-8b61-997bc02d77c6.jpeg"
)
GOOD_ALT = "https://a0.muscache.com/im/pictures/073abbed-baf2-4f1c-a3f8-da9a6df64b9d.jpg"


class TestAirbnbPictureExtraction(unittest.TestCase):
    def test_hero_prefers_data_original_uri(self):
        body = f"""
        <div data-section-id="HERO_DEFAULT">
          <picture>
            <img data-original-uri="{GOOD_HERO_URI}" alt="" />
          </picture>
        </div>
        """
        r = _html_response(body)
        self.assertEqual(_extract_picture_url_from_hero_html(r), GOOD_HERO_URI)
        self.assertEqual(extract_picture_url(r, ""), GOOD_HERO_URI)

    def test_hero_ignores_banned_then_takes_next_in_hero(self):
        bad = "https://a0.muscache.com/im/pictures/foo/AirbnbPlatformAssets/bar.jpg"
        body = f"""
        <section data-section-id="HERO_DEFAULT">
          <img data-original-uri="{bad}" />
          <img data-original-uri="{GOOD_ALT}" />
        </section>
        """
        r = _html_response(body)
        self.assertEqual(extract_picture_url(r, ""), GOOD_ALT)

    def test_prefers_hero_over_bad_payload(self):
        payload = json.dumps(
            {
                "baseUrl": (
                    "https://a0.muscache.com/im/pictures/"
                    "Review-AI-Synthesis/synthetic.png"
                ),
                "pictureUrl": GOOD_ALT,
            }
        )
        body = f"""
        <div data-section-id="HERO_DEFAULT">
          <img data-original-uri="{GOOD_HERO_URI}" />
        </div>
        """
        r = _html_response(body)
        self.assertEqual(extract_picture_url(r, payload), GOOD_HERO_URI)

    def test_payload_rejects_banned_even_when_first_match(self):
        payload = (
            '{"baseUrl":"https://a0.muscache.com/im/pictures/x/AirbnbPlatformAssets/y.jpg",'
            '"pictureUrl":"' + GOOD_ALT + '"}'
        )
        self.assertEqual(_extract_picture_url_from_payload(payload), GOOD_ALT)

    def test_page_wide_original_uri_when_no_hero_section(self):
        body = f'<html><body><img data-original-uri="{GOOD_ALT}" /></body></html>'
        r = _html_response(body)
        self.assertEqual(_extract_picture_url_from_hero_html(r), "")
        self.assertEqual(_extract_picture_url_from_page_original_uri(r), GOOD_ALT)
        self.assertEqual(extract_picture_url(r, ""), GOOD_ALT)

    def test_fallback_json_when_no_dom_images(self):
        payload = '{"pictureUrl":"' + GOOD_ALT + '"}'
        r = _html_response("<html><body></body></html>")
        self.assertEqual(extract_picture_url(r, payload), GOOD_ALT)

    def test_banned_substrings_constant(self):
        self.assertIn("AirbnbPlatformAssets", BANNED_PICTURE_URL_SUBSTRINGS)
        self.assertIn("Review-AI-Synthesis", BANNED_PICTURE_URL_SUBSTRINGS)

    def test_is_banned_picture_url(self):
        cases = [
            (
                "https://a0.muscache.com/im/pictures/a/AirbnbPlatformAssets/x.jpg",
                True,
            ),
            (
                "https://a0.muscache.com/im/pictures/Review-AI-Synthesis/foo.png",
                True,
            ),
            (GOOD_ALT, False),
        ]
        for url, banned in cases:
            with self.subTest(url=url):
                self.assertEqual(is_banned_picture_url(url), banned)


if __name__ == "__main__":
    unittest.main()
