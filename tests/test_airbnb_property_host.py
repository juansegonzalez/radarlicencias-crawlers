"""Tests for listing title and host extraction (DOM-first, conservative)."""

import unittest

from scrapy.http import HtmlResponse

from radarlicencias.spiders.airbnb_mallorca import (
    _extract_host_fields_with_source,
    _extract_property_name_with_source,
    _extract_max_guests_with_source,
)


def _resp(url: str, body: str) -> HtmlResponse:
    return HtmlResponse(url=url, body=body.encode("utf-8"), encoding="utf-8")


class TestPropertyNameExtraction(unittest.TestCase):
    def test_title_default_section_wins(self):
        body = """
        <div data-section-id="TITLE_DEFAULT"><h1>  Sea view flat  </h1></div>
        <script>{"name":"StaysSearch","title":"ignore"}</script>
        """
        name, src = _extract_property_name_with_source(_resp("https://www.airbnb.com/rooms/1", body))
        self.assertEqual(name, "Sea view flat")
        self.assertEqual(src, "dom_title_section")

    def test_listing_title_json_key(self):
        # Wrap JSON in HTML so Scrapy does not treat the response as JSON-only (css() would fail).
        body = '<html><body><script type="application/json">{"listingTitle":"Cozy Finca","foo":"bar"}</script></body></html>'
        name, src = _extract_property_name_with_source(_resp("https://www.airbnb.com/rooms/2", body))
        self.assertEqual(name, "Cozy Finca")
        self.assertEqual(src, "embedded_listing_json")

    def test_rejects_generic_search_metadata(self):
        body = '<html><body>{"name":"StaysSearch","title":"operationName"}</body></html>'
        name, src = _extract_property_name_with_source(_resp("https://www.airbnb.com/rooms/3", body))
        self.assertEqual(name, "")
        self.assertEqual(src, "none")

    def test_rejects_ab_test_treatment_token(self):
        """Legacy name/title scan must not pick experiment flags as listing title."""
        body = '<html><body>{"name":"treatment","listingTitle":"Real Title Here"}</body></html>'
        name, src = _extract_property_name_with_source(_resp("https://www.airbnb.com/rooms/4", body))
        self.assertEqual(name, "Real Title Here")
        self.assertEqual(src, "embedded_listing_json")


class TestHostExtraction(unittest.TestCase):
    def test_host_overview_hosted_by_miquel(self):
        body = """
        <section data-section-id="HOST_OVERVIEW_DEFAULT">
          <span>Hosted by Miquel</span>
          <a href="/users/show/999">profile</a>
        </section>
        """
        h = _extract_host_fields_with_source(
            _resp("https://www.airbnb.com/rooms/10", body), body
        )
        self.assertEqual(h["host_name"], "Miquel")
        self.assertEqual(h["host_url"], "https://www.airbnb.com/users/show/999")
        self.assertEqual(h["host_source"], "dom_host_overview")

    def test_meet_your_host_years_spanish(self):
        body = """
        <section data-section-id="MEET_YOUR_HOST">
          <span>Anfitrionado por Carla</span>
          <span>5 años como anfitrión</span>
        </section>
        """
        h = _extract_host_fields_with_source(
            _resp("https://www.airbnb.com/rooms/11", body), "{}"
        )
        self.assertEqual(h["host_name"], "Carla")
        self.assertEqual(h["host_years_hosting"], 5)
        self.assertEqual(h["host_source"], "dom_meet_your_host")

    def test_cohost_not_used_as_main_name(self):
        body = """
        <section data-section-id="HOST_OVERVIEW_DEFAULT">
          <span>Hosted by Anna</span>
          <span>Co-hosted by Zoe</span>
        </section>
        """
        h = _extract_host_fields_with_source(
            _resp("https://www.airbnb.com/rooms/12", body), "{}"
        )
        self.assertEqual(h["host_name"], "Anna")

    def test_no_superhost_in_simple_dom(self):
        body = """
        <section data-section-id="HOST_OVERVIEW_DEFAULT">
          <span>Hosted by Pau</span>
        </section>
        """
        h = _extract_host_fields_with_source(
            _resp("https://www.airbnb.com/rooms/13", body), "{}"
        )
        self.assertFalse(h["host_is_superhost"])


class TestMaxGuestsLocalization(unittest.TestCase):
    def test_spanish_huespedes_in_overview(self):
        body = """
        <section data-section-id="OVERVIEW_DEFAULT_V2">
          <ol><li>4 huéspedes</li><li>2 habitaciones</li></ol>
        </section>
        """
        val, src = _extract_max_guests_with_source(_resp("https://www.airbnb.com/rooms/20", body), body)
        self.assertEqual(val, "4")
        self.assertEqual(src, "overview_dom")


if __name__ == "__main__":
    unittest.main()
