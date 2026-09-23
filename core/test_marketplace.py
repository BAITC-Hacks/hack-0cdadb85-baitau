"""User submissions use the existing contract; no marketplace storage is required."""

from copy import deepcopy
import unittest

from core import run_pipeline
from core.test_generator import request
from helpers.utils import load_contractors, safe_pipeline_call, validate_output


class MarketplaceIntegrationTests(unittest.TestCase):
    def setUp(self):
        self.base = load_contractors()
        self.query = request()
        self.submitted = {
            "id": "USR-00001", "anon_name": "Nova Photo",
            "categories": ["Фотограф"], "city": "Алматы",
            "price_from_kzt": 100000, "event_formats": ["свадьба"],
            "languages": ["русский"], "max_hours": 12, "busy_dates": [],
            "description": "Свадебная фотография",
            "synthetic": True, "city_imputed": False, "price_imputed": False,
        }
        self.combined = self.base + [self.submitted]

    def test_combined_catalog_recommends_submission_through_helpers(self):
        self.assertEqual(len(self.base), 66)
        self.assertEqual(len(self.combined), 67)
        before = deepcopy(self.combined)
        result = run_pipeline(self.query, self.combined)
        self.assertEqual(result["status"], "matched")
        self.assertTrue(validate_output(result))
        self.assertLessEqual(len(result["results"]), 3)
        self.assertIn(self.submitted["id"], [c["id"] for c in result["results"]])
        safe = safe_pipeline_call(run_pipeline, self.query, self.combined)
        self.assertIs(safe["fallback"], False)
        self.assertEqual(safe, dict(result, fallback=False))
        self.assertEqual(self.combined, before)
        self.assertEqual(load_contractors(), self.base)

    def test_submission_obeys_each_hard_filter(self):
        changes = [
            {"city": "Астана"}, {"categories": ["Флорист"]},
            {"busy_dates": [self.query["date"]]}, {"event_formats": ["корпоратив"]},
            {"price_from_kzt": 400001}, {"languages": ["казахский"]}, {"max_hours": 7},
        ]
        baseline = run_pipeline(self.query, self.base)
        for change in changes:
            with self.subTest(change=change):
                catalog = self.base + [dict(self.submitted, **change)]
                result = run_pipeline(self.query, catalog)
                self.assertNotIn(self.submitted["id"], [c["id"] for c in result["results"]])
                self.assertEqual(result["results"], baseline["results"])

    def test_combined_catalog_is_deterministic_and_order_independent(self):
        runs = [run_pipeline(self.query, self.combined) for _ in range(5)]
        expected_ids = [c["id"] for c in runs[0]["results"]]
        self.assertIn(self.submitted["id"], expected_ids)
        for result in runs:
            self.assertEqual([c["id"] for c in result["results"]], expected_ids)
            self.assertEqual(result, runs[0])
        self.assertEqual(run_pipeline(self.query, self.combined[::-1]), runs[0])

    def test_submission_preserves_missing_category_status(self):
        query = request(city="Зарубежье", category="Шоу-программа")
        result = run_pipeline(query, self.combined)
        self.assertEqual(result["status"], "no_category_in_city")
        self.assertEqual(result, run_pipeline(query, self.base))

    def test_rejected_submission_contributes_all_diagnostics(self):
        query = request(budget_kzt=50000)
        rejected = dict(self.submitted, busy_dates=[query["date"]],
                        event_formats=["корпоратив"], languages=["казахский"], max_hours=7)
        result = run_pipeline(query, self.base + [rejected])
        self.assertEqual(result["status"], "no_eligible_candidates")
        self.assertEqual(result["results"], [])
        baseline = run_pipeline(query, self.base)
        expected_meta = deepcopy(baseline["meta"])
        expected_meta["catalog_candidates"] += 1
        for key in expected_meta["diagnostics"]:
            expected_meta["diagnostics"][key] += 1
        self.assertEqual(result["meta"], expected_meta)
        safe = safe_pipeline_call(run_pipeline, query, self.base + [rejected])
        self.assertEqual(safe, dict(result, fallback=False))

    def test_submission_explanation_and_provenance_are_factual(self):
        result = run_pipeline(self.query, self.combined)
        card = next(c for c in result["results"] if c["id"] == self.submitted["id"])
        self.assertEqual(card["name"], self.submitted["anon_name"])
        for key in ("city", "price_from_kzt", "event_formats", "languages", "max_hours",
                    "description", "synthetic", "city_imputed", "price_imputed"):
            self.assertEqual(card[key], self.submitted[key])
        self.assertIs(card["synthetic"], True)
        self.assertIsInstance(card["explanation"], str)
        for fact in ("2026-11-14", "Алматы", "Фотограф", "свадьба", "от 100 000 ₸",
                     "бюджете 400 000 ₸", "300 000 ₸", "русский", "12 ч", "8 ч"):
            self.assertIn(fact, card["explanation"])

    def test_submission_id_prefix_does_not_change_recommendation(self):
        result = run_pipeline(self.query, self.combined)
        renamed = dict(self.submitted, id="HK-TEST-SUBMISSION")
        ordinary = run_pipeline(self.query, self.base + [renamed])
        expected = deepcopy(result)
        for card in expected["results"]:
            if card["id"] == self.submitted["id"]:
                card["id"] = renamed["id"]
        self.assertEqual(ordinary, expected)


if __name__ == "__main__":
    unittest.main()
