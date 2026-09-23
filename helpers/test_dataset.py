"""Smoke checks against the organizer's actual source data."""

import csv
import unittest
from datetime import date
from pathlib import Path

from .utils import load_contractors, load_mock_data, safe_pipeline_call, validate_contractor, validate_output


class DatasetTests(unittest.TestCase):
    def test_catalog_matches_source(self):
        contractors = load_contractors()
        self.assertEqual(len(contractors), 66)
        self.assertEqual(len({c["id"] for c in contractors}), 66)
        source = Path(__file__).resolve().parents[1] / "given_data" / "hackathon dataset anonymized .csv"
        with source.open(encoding="utf-8-sig", newline="") as stream:
            raw = {c["id"]: c for c in csv.DictReader(stream)}
        self.assertEqual(set(raw), {c["id"] for c in contractors})
        for c in contractors:
            self.assertTrue(validate_contractor(c))
            self.assertEqual(c["busy_dates"], raw[c["id"]]["busy_dates"].split("|"))
            for field in ("categories", "event_formats", "languages"):
                self.assertEqual(c[field], raw[c["id"]][field].split("|"))
            for flag in ("synthetic", "city_imputed", "price_imputed"):
                self.assertEqual(c[flag], raw[c["id"]][flag] == "True")
            self.assertEqual(c["price_from_kzt"], int(raw[c["id"]]["price_from_kzt"]))
            self.assertIs(type(c["price_from_kzt"]), int)
            for value in c["busy_dates"]:
                self.assertEqual(date.fromisoformat(value).isoformat(), value)

    def test_real_mock_and_core_failure(self):
        contractors = load_contractors()
        by_id = {c["id"]: c for c in contractors}
        mock = load_mock_data()
        self.assertTrue(validate_output(mock))
        self.assertEqual(mock["status"], "matched")
        query = mock["query"]
        for card in mock["results"]:
            c = by_id[card["id"]]
            self.assertEqual(c["city"], query["city"])
            self.assertEqual(card["name"], c["anon_name"])
            self.assertIn(query["category"], c["categories"])
            self.assertIn(query["event_format"], c["event_formats"])
            self.assertIn(query["language"], c["languages"])
            self.assertLessEqual(c["price_from_kzt"], query["budget_kzt"])
            self.assertNotIn(query["date"], c["busy_dates"])
            self.assertTrue(c["max_hours"] is None or c["max_hours"] >= query["duration_hours"])
        self.assertEqual(len({c["explanation"] for c in mock["results"]}), len(mock["results"]))

        def broken(*args):
            raise RuntimeError("LLM unavailable")

        result = safe_pipeline_call(broken, query, contractors)
        self.assertEqual(result["status"], "matched")
        self.assertIs(result["fallback"], True)


if __name__ == "__main__":
    unittest.main()
