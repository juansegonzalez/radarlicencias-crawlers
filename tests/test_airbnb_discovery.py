"""Tests for StaysSearch payload helpers (no live HTTP)."""

import json
import unittest

from radarlicencias.spiders.airbnb_mallorca import (
    RISKY_LEAF_MAX_OFFSET,
    STAYSSEARCH_PAGE_SIZE,
    _build_stayssearch_payload,
)


class TestStaysSearchPayload(unittest.TestCase):
    def test_items_offset_appended_to_raw_params(self):
        p = _build_stayssearch_payload(39.2, 2.3, 39.9, 3.4, items_offset=18)
        raw = p["variables"]["staysSearchRequest"]["rawParams"]
        names = [x.get("filterName") for x in raw]
        self.assertIn("itemsOffset", names)
        off = next(x for x in raw if x.get("filterName") == "itemsOffset")
        self.assertEqual(off["filterValues"], ["18"])

    def test_zero_offset_omits_items_offset(self):
        p = _build_stayssearch_payload(39.2, 2.3, 39.9, 3.4, items_offset=0)
        raw = p["variables"]["staysSearchRequest"]["rawParams"]
        names = [x.get("filterName") for x in raw]
        self.assertNotIn("itemsOffset", names)

    def test_map_v2_includes_items_offset_when_paginating(self):
        p = _build_stayssearch_payload(39.2, 2.3, 39.9, 3.4, items_offset=36)
        raw = p["variables"]["staysMapSearchRequestV2"]["rawParams"]
        names = [x.get("filterName") for x in raw]
        self.assertIn("itemsOffset", names)

    def test_payload_json_serializable(self):
        p = _build_stayssearch_payload(39.2, 2.3, 39.9, 3.4, items_offset=18)
        json.dumps(p)


class TestDiscoveryConstants(unittest.TestCase):
    def test_page_size_matches_offset_cap(self):
        self.assertEqual(RISKY_LEAF_MAX_OFFSET % STAYSSEARCH_PAGE_SIZE, 0)


if __name__ == "__main__":
    unittest.main()
