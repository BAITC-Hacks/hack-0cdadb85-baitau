"""Run with: python -B -m unittest core.test_generator -v."""

from copy import deepcopy
import json
import unittest
from unittest.mock import patch

from core import run_pipeline
from core.generator import build_verified_facts, calculate_score


def request(**changes):
    return dict(city="Алматы", date="2026-11-14", event_format="свадьба",
                category="Фотограф", budget_kzt=400000,
                duration_hours=8, language="русский") | changes


def contractor(identifier="HK-001", **changes):
    return dict(id=identifier, anon_name="Фото " + identifier, city="Алматы",
                categories=["Фотограф"], price_from_kzt=300000,
                event_formats=["свадьба"], languages=["русский"], max_hours=10,
                busy_dates=[], description="Свадебный репортаж",
                synthetic=False, city_imputed=False, price_imputed=False) | changes


class PipelineTests(unittest.TestCase):
    def test_normal_contract_and_limit(self):
        result = run_pipeline(request(), [contractor(str(i)) for i in range(5)])
        self.assertEqual(result["status"], "matched")
        self.assertEqual(len(result["results"]), 3)
        self.assertEqual(result["meta"], dict(catalog_candidates=5,
                         eligible_candidates=5, returned=3, diagnostics={}))
        self.assertEqual(set(result["results"][0]), {
            "id", "name", "category", "city", "price_from_kzt", "event_formats",
            "languages", "max_hours", "description", "synthetic", "city_imputed",
            "price_imputed", "score", "explanation",
        })
        json.dumps(result, allow_nan=False)

    def test_deterministic_even_when_catalog_reversed(self):
        catalog = [contractor("B"), contractor("A"), contractor("C", price_from_kzt=200000)]
        first = run_pipeline(request(), catalog)
        self.assertEqual(first, run_pipeline(request(), catalog))
        self.assertEqual(first, run_pipeline(request(), catalog[::-1]))
        self.assertEqual([c["id"] for c in first["results"]], ["C", "A", "B"])

    def test_busy_date_changes_result(self):
        catalog = [contractor(busy_dates=["2026-11-14"])]
        self.assertEqual(run_pipeline(request(), catalog)["results"], [])
        next_day = run_pipeline(request(date="2026-11-15"), catalog)
        self.assertEqual(next_day["results"][0]["id"], "HK-001")

    def test_impossible_budget(self):
        result = run_pipeline(request(budget_kzt=1), [contractor()])
        self.assertEqual(result["status"], "no_eligible_candidates")
        self.assertEqual(result["meta"]["diagnostics"]["over_budget"], 1)

    def test_no_category_in_city(self):
        for catalog in ([], [contractor(city="Астана")], [contractor(categories=["Флорист"]) ]):
            with self.subTest(catalog=catalog):
                result = run_pipeline(request(), catalog)
                self.assertEqual(result["status"], "no_category_in_city")
                self.assertEqual(result["meta"]["diagnostics"], {})

    def test_all_failures_counted_only_in_requested_pool(self):
        bad = contractor(busy_dates=["2026-11-14"], price_from_kzt=500000,
                         event_formats=["концерт"], languages=["казахский"], max_hours=6)
        result = run_pipeline(request(), [bad, dict(bad, id="other", city="Астана")])
        self.assertEqual(result["status"], "no_eligible_candidates")
        self.assertEqual(result["meta"]["catalog_candidates"], 1)
        self.assertEqual(result["meta"]["diagnostics"], {
            "busy_on_date": 1, "over_budget": 1, "unsupported_format": 1,
            "unsupported_language": 1, "duration_too_long": 1,
        })

    def test_each_hard_filter_independently(self):
        for change in (dict(busy_dates=["2026-11-14"]), dict(price_from_kzt=400001),
                       dict(event_formats=[]), dict(languages=[]), dict(max_hours=6)):
            with self.subTest(change=change):
                self.assertEqual(run_pipeline(request(), [contractor(**change)])["results"], [])

    def test_duration_ten_hours(self):
        result = run_pipeline(request(duration_hours=10), [contractor(max_hours=6)])
        self.assertEqual(result["meta"]["diagnostics"]["duration_too_long"], 1)

    def test_florist_without_hour_limit(self):
        row = contractor(categories=["Флорист"], max_hours=None)
        result = run_pipeline(request(category="Флорист", duration_hours=10), [row])
        self.assertEqual(result["status"], "matched")
        self.assertIn("лимит в профиле не указан", result["results"][0]["explanation"])
        self.assertIsNone(build_verified_facts(row, request())["duration_match"])

    def test_boundary_budget_duration_and_score(self):
        row = contractor(price_from_kzt=400000, max_hours=8)
        self.assertEqual(run_pipeline(request(), [row])["status"], "matched")
        self.assertAlmostEqual(calculate_score(row, request()), 0.25 + 0.2 / 1.5)

    def test_optional_fields_absent_or_none(self):
        query = request()
        del query["language"]
        del query["duration_hours"]
        row = contractor(languages=[], max_hours=1)
        result = run_pipeline(query, [row])
        self.assertEqual(result, run_pipeline(request(language=None, duration_hours=None), [row]))
        text = result["results"][0]["explanation"]
        self.assertNotIn("язык", text)
        self.assertNotIn(" ч", text)

    def test_explanation_and_provenance(self):
        row = contractor(synthetic=True, city_imputed=True, price_imputed=True)
        found = run_pipeline(request(), [row])["results"][0]
        for flag in ("synthetic", "city_imputed", "price_imputed"):
            self.assertTrue(found[flag])
        for fact in ("2026-11-14", "Алматы", "свадьба", "300 000", "400 000",
                     "100 000", "русский", "10 ч", "8 ч"):
            self.assertIn(fact, found["explanation"])

    def test_no_input_or_output_alias_mutation(self):
        query, catalog = request(), [contractor()]
        original = deepcopy((query, catalog))
        output = run_pipeline(query, catalog)
        self.assertEqual((query, catalog), original)
        output["results"][0]["languages"].clear()
        output["query"]["city"] = "other"
        self.assertEqual((query, catalog), original)

    def test_invalid_requests(self):
        for change in (dict(date="2026-02-30"), dict(date="20261114"),
                       dict(city=""), dict(category=None), dict(budget_kzt=0),
                       dict(budget_kzt=-1), dict(budget_kzt=True), dict(budget_kzt=1.5),
                       dict(duration_hours=0), dict(duration_hours=float("nan")),
                       dict(duration_hours=float("inf")), dict(duration_hours=True),
                       dict(language=[]), dict(language=" ")):
            with self.subTest(change=change), self.assertRaises(ValueError):
                run_pipeline(request(**change), [])
        for field in ("city", "date", "event_format", "category", "budget_kzt"):
            query = request()
            del query[field]
            with self.subTest(field=field), self.assertRaises(ValueError):
                run_pipeline(query, [])

    def test_offline_no_api_dependency(self):
        with patch("socket.socket", side_effect=OSError("network unavailable")):
            self.assertEqual(run_pipeline(request(), [contractor()])["status"], "matched")

    def test_explanations_only_for_top_three(self):
        with patch("core.generator.generate_explanation", return_value="facts") as explain:
            run_pipeline(request(), [contractor(str(i)) for i in range(66)])
        self.assertEqual(explain.call_count, 3)


if __name__ == "__main__":
    unittest.main()
