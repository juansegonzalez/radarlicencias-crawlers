"""Tests for Airbnb listing max_guests extraction (overview vs JSON vs description)."""

import unittest

from scrapy.http import HtmlResponse

from radarlicencias.spiders.airbnb_mallorca import (
    AIRBNB_MAX_LISTING_GUEST_CAPACITY,
    _extract_max_guests,
    _extract_max_guests_meta,
    _extract_max_guests_with_source,
)


def _html_response(body: str) -> HtmlResponse:
    return HtmlResponse(
        url="https://www.airbnb.com/rooms/12345",
        body=body.encode("utf-8"),
        encoding="utf-8",
    )


class TestAirbnbMaxGuestsExtraction(unittest.TestCase):
    def test_overview_wins_over_description_with_larger_guest_mention(self):
        body = """
        <section data-section-id="OVERVIEW_DEFAULT_V2">
          <ol>
            <li>6 guests</li>
            <li>4 bedrooms</li>
            <li>5 beds</li>
            <li>3 baths</li>
          </ol>
        </section>
        <div>
          <p>Perfect for an event for up to 50 guests in our garden.</p>
        </div>
        """
        self.assertEqual(_extract_max_guests(_html_response(body)), "6")

    def test_overview_v1_section_id(self):
        body = """
        <section data-section-id="OVERVIEW_DEFAULT">
          <ol><li>4 guests</li><li>2 bedrooms</li></ol>
        </section>
        """
        self.assertEqual(_extract_max_guests(_html_response(body)), "4")

    def test_fallback_before_description_section(self):
        """No overview block: regex runs only on text before DESCRIPTION, not description body."""
        body = """
        <header><span>4 guests</span> · Palma</header>
        <section data-section-id="DESCRIPTION_DEFAULT">
          <p>We host weddings up to 50 guests.</p>
        </section>
        """
        self.assertEqual(_extract_max_guests(_html_response(body)), "4")

    def test_no_guest_value_returns_empty(self):
        body = """
        <section data-section-id="OVERVIEW_DEFAULT_V2">
          <ol><li>2 bedrooms</li></ol>
        </section>
        """
        self.assertEqual(_extract_max_guests(_html_response(body)), "")

    def test_malformed_html_does_not_raise(self):
        body = (
            '<section data-section-id="OVERVIEW_DEFAULT_V2">'
            "<ol><li>3 guests<li></ol></section>"
        )
        try:
            out = _extract_max_guests(_html_response(body))
        except Exception as e:  # pragma: no cover
            self.fail(f"extract raised: {e}")
        self.assertEqual(out, "3")

    def test_provenance_overview_dom(self):
        body = """
        <section data-section-id="OVERVIEW_DEFAULT_V2"><ol><li>2 guests</li></ol></section>
        """
        val, src, st = _extract_max_guests_meta(_html_response(body), body)
        self.assertEqual(val, "2")
        self.assertEqual(src, "overview_dom")
        self.assertEqual(st, "valid")

    def test_provenance_limited_regex(self):
        body = """
        <header><span>3 guests</span></header>
        <section data-section-id="DESCRIPTION_DEFAULT"><p>50 guests at party</p></section>
        """
        val, src, st = _extract_max_guests_meta(_html_response(body), body)
        self.assertEqual(val, "3")
        self.assertEqual(src, "limited_regex")
        self.assertEqual(st, "fallback_used")

    def test_embedded_json_person_capacity_when_no_overview(self):
        body = """
        <html><script>{"personCapacity":8,"foo":1}</script>
        <section data-section-id="DESCRIPTION_DEFAULT"><p>up to 50 guests for events</p></section></html>
        """
        r = _html_response(body)
        val, src, st = _extract_max_guests_meta(r, body)
        self.assertEqual(val, "8")
        self.assertEqual(src, "embedded_json")
        self.assertEqual(st, "valid")

    def test_rejects_capacity_above_airbnb_limit(self):
        body = """
        <section data-section-id="OVERVIEW_DEFAULT_V2"><ol><li>20 guests</li></ol></section>
        """
        val, src, st = _extract_max_guests_meta(_html_response(body), body)
        self.assertEqual(val, "")
        self.assertEqual(src, "overview_dom")
        self.assertEqual(st, "above_airbnb_limit")

    def test_json_capacity_rejects_over_limit(self):
        body = '{"personCapacity":17}'
        r = _html_response(f"<html>{body}</html>")
        val, src, st = _extract_max_guests_meta(r, f"<html>{body}</html>")
        self.assertEqual(val, "")
        self.assertEqual(st, "above_airbnb_limit")

    def test_overview_wins_before_json(self):
        body = """
        <section data-section-id="OVERVIEW_DEFAULT_V2"><ol><li>5 guests</li></ol></section>
        {"personCapacity":9}
        """
        r = _html_response(body)
        val, src, st = _extract_max_guests_meta(r, body)
        self.assertEqual(val, "5")
        self.assertEqual(src, "overview_dom")

    def test_cap_constant_is_16(self):
        self.assertEqual(AIRBNB_MAX_LISTING_GUEST_CAPACITY, 16)


if __name__ == "__main__":
    unittest.main()
