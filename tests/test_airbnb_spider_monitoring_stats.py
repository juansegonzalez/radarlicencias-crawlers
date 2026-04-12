"""Lightweight tests for airbnb_mallorca production monitoring stats (no crawl)."""

import unittest
from unittest.mock import MagicMock

from radarlicencias.items import AirbnbListingItem
from radarlicencias.spiders.airbnb_mallorca import _record_airbnb_detail_monitoring_stats


class _DummyStats:
    def __init__(self):
        self.counts = {}

    def inc_value(self, key: str, value: int = 1) -> None:
        self.counts[key] = self.counts.get(key, 0) + value

    def get_value(self, key: str):
        return self.counts.get(key, 0)


class TestAirbnbMonitoringStats(unittest.TestCase):
    def _spider(self):
        sp = MagicMock()
        sp.logger = MagicMock()
        sp.crawler = MagicMock()
        sp.crawler.stats = _DummyStats()
        return sp

    def test_happy_path_increments_core_counters(self):
        spider = self._spider()
        st = spider.crawler.stats
        item = AirbnbListingItem(
            url="https://www.airbnb.com/rooms/1",
            latitude=39.5,
            longitude=2.7,
            registration_number="ETV1234",
            registration_number_source="mallorca_regional_label",
            property_name="Nice place in Palma, Spain",
            max_guests="4",
            max_guests_source="embedded_json",
            max_guests_validation_status="valid",
        )
        _record_airbnb_detail_monitoring_stats(spider, item)

        self.assertEqual(st.counts.get("airbnb_mallorca/items_total"), 1)
        self.assertEqual(st.counts.get("airbnb_mallorca/items_with_registration"), 1)
        self.assertEqual(st.counts.get("airbnb_mallorca/coordinates_present"), 1)
        self.assertEqual(st.counts.get("airbnb_mallorca/max_guests_source_embedded_json"), 1)
        self.assertEqual(st.counts.get("airbnb_mallorca/registration_source_mallorca_regional_label"), 1)

    def test_missing_fields_and_max_guests_validation(self):
        spider = self._spider()
        st = spider.crawler.stats
        item = AirbnbListingItem(
            url="https://www.airbnb.com/rooms/2",
            latitude=None,
            longitude=None,
            registration_number="",
            registration_number_source="none",
            property_name="",
            max_guests="20",
            max_guests_source="overview_dom",
            max_guests_validation_status="valid",
        )
        _record_airbnb_detail_monitoring_stats(spider, item)

        self.assertEqual(st.counts.get("airbnb_mallorca/items_missing_coordinates"), 1)
        self.assertEqual(st.counts.get("airbnb_mallorca/coordinates_missing"), 1)
        self.assertEqual(st.counts.get("airbnb_mallorca/items_missing_registration"), 1)
        self.assertEqual(st.counts.get("airbnb_mallorca/items_missing_title"), 1)
        self.assertEqual(st.counts.get("airbnb_mallorca/max_guests_value_above_16"), 1)
        self.assertEqual(st.counts.get("airbnb_mallorca/max_guests_source_overview_dom"), 1)
        self.assertEqual(st.counts.get("airbnb_mallorca/registration_source_none"), 1)


if __name__ == "__main__":
    unittest.main()
