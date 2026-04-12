"""Tests for Airbnb listing max_guests extraction (overview vs description)."""

import unittest

from scrapy.http import HtmlResponse

from radarlicencias.spiders.airbnb_mallorca import _extract_max_guests


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


if __name__ == "__main__":
    unittest.main()
