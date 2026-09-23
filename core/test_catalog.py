"""Integration checks against the shared source catalog, without UI dependencies."""

import csv
from pathlib import Path
import unittest

from core import run_pipeline
from core.test_generator import request
from helpers.utils import load_contractors, normalize_request, safe_pipeline_call, validate_output


CATALOG_PATH = Path(__file__).resolve().parents[1] / "given_data" / "hackathon dataset anonymized .csv"


class SharedCatalogTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Test-only conversion. The production loader belongs to helpers.
        with CATALOG_PATH.open(encoding="utf-8-sig", newline="") as source:
            cls.catalog = list(csv.DictReader(source))
        for row in cls.catalog:
            for key in ("categories", "event_formats", "languages", "busy_dates"):
                row[key] = row[key].split("|") if row[key] else []
            row["price_from_kzt"] = int(row["price_from_kzt"])
            row["max_hours"] = int(row["max_hours"]) if row["max_hours"] else None
            for key in ("synthetic", "city_imputed", "price_imputed"):
                if row[key] not in ("True", "False"):
                    raise ValueError(f"Unexpected boolean in {key}: {row[key]!r}")
                row[key] = row[key] == "True"

    def test_catalog_schema(self):
        self.assertEqual(len(self.catalog), 66)
        self.assertEqual(len({row["id"] for row in self.catalog}), 66)
        for row in self.catalog:
            self.assertGreaterEqual(row["price_from_kzt"], 0)
            self.assertTrue(row["categories"])
            self.assertTrue(row["event_formats"])

    def test_helpers_loader_preserves_source(self):
        expected = {row["id"]: row for row in self.catalog}
        actual = {row["id"]: row for row in load_contractors()}
        self.assertEqual(actual, expected)

    def test_helpers_wrapper_with_real_catalog(self):
        catalog = load_contractors()
        cases = [
            (request(), "matched"),
            (request(date="2026-11-15"), "matched"),
            (request(budget_kzt=1), "no_eligible_candidates"),
            (request(city="missing-city"), "no_category_in_city"),
            (request(language=None, duration_hours=None), "matched"),
            (request(date="14.11.2026", budget_kzt="400 000 ₸", duration_hours="8"), "matched"),
        ]
        for query, status in cases:
            with self.subTest(query=query):
                result = safe_pipeline_call(run_pipeline, query, catalog)
                self.assertFalse(result["fallback"])
                self.assertTrue(validate_output(result))
                self.assertEqual(result["status"], status)
                expected = run_pipeline(normalize_request(query), self.catalog)
                self.assertEqual(result, dict(expected, fallback=False))

    def test_demo_dates(self):
        expected = {
            "2026-11-14": ["HK-68220", "HK-76268", "HK-91112"],
            "2026-11-15": ["HK-68220", "HK-91112"],
        }
        for day, identifiers in expected.items():
            with self.subTest(day=day):
                query = request(date=day)
                result = run_pipeline(query, self.catalog)
                self.assertEqual(result["status"], "matched")
                self.assertEqual([row["id"] for row in result["results"]], identifiers)
                self.assertEqual(result, run_pipeline(query, self.catalog[::-1]))
                self.assertEqual(result["meta"]["catalog_candidates"], 8)

    def test_demo_date_change_is_caused_by_busy_dates(self):
        day_a, day_b = "2026-11-14", "2026-11-15"
        ids_a = [c["id"] for c in run_pipeline(request(date=day_a), self.catalog)["results"]]
        ids_b = [c["id"] for c in run_pipeline(request(date=day_b), self.catalog)["results"]]
        self.assertEqual(set(ids_a) - set(ids_b), {"HK-76268"})
        contractor = next(c for c in self.catalog if c["id"] == "HK-76268")
        self.assertNotIn(day_a, contractor["busy_dates"])
        self.assertIn(day_b, contractor["busy_dates"])
        available = dict(contractor, busy_dates=[d for d in contractor["busy_dates"] if d != day_b])
        catalog = [available if c["id"] == contractor["id"] else c for c in self.catalog]
        restored = run_pipeline(request(date=day_b), catalog)
        self.assertEqual([c["id"] for c in restored["results"]], ids_a)

    def test_every_busy_date_excludes_contractor(self):
        for row in self.catalog:
            for day in row["busy_dates"]:
                query = request(city=row["city"], category=row["categories"][0],
                                event_format=row["event_formats"][0], date=day,
                                budget_kzt=max(1, row["price_from_kzt"]),
                                language=None, duration_hours=None)
                result = run_pipeline(query, self.catalog)
                with self.subTest(identifier=row["id"], day=day):
                    self.assertNotIn(row["id"], [c["id"] for c in result["results"]])
                    self.assertLessEqual(len(result["results"]), 3)

    def test_demo_low_budget_diagnostics_through_helpers(self):
        result = safe_pipeline_call(run_pipeline, request(budget_kzt=50000), load_contractors())
        self.assertIs(result["fallback"], False)
        self.assertEqual(result["status"], "no_eligible_candidates")
        self.assertEqual(result["results"], [])
        self.assertEqual(result["meta"], {
            "catalog_candidates": 8, "eligible_candidates": 0, "returned": 0,
            "diagnostics": {
                "busy_on_date": 5, "over_budget": 8, "unsupported_format": 2,
                "unsupported_language": 0, "duration_too_long": 2,
            },
        })

    def test_impossible_budget_and_missing_city(self):
        result = run_pipeline(request(budget_kzt=1), self.catalog)
        self.assertEqual(result["status"], "no_eligible_candidates")
        self.assertEqual(result["meta"]["diagnostics"]["over_budget"], 8)
        self.assertEqual(run_pipeline(request(city="missing-city"), self.catalog)["status"],
                         "no_category_in_city")


if __name__ == "__main__":
    unittest.main()
