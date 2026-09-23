"""Integration checks; run when the team's core package is available."""

import unittest

try:
    from core.generator import run_pipeline
except ModuleNotFoundError as exc:
    if exc.name not in {"core", "core.generator"}:
        raise
    run_pipeline = None

from .utils import normalize_contractor, safe_pipeline_call, validate_output


@unittest.skipIf(run_pipeline is None, "Core package not present in this checkout")
class CoreIntegrationTests(unittest.TestCase):
    def setUp(self):
        self.query = dict(city="Алматы", date="2026-11-14", event_format="свадьба",
                          category="Фотограф", budget_kzt="400 000 ₸")
        self.contractor = normalize_contractor(dict(
            id="TEST-ONLY", anon_name="Integration fixture", city="Алматы",
            categories="['Фотограф']", price_from_kzt="300000.0",
            event_formats='["свадьба"]', languages=["русский"],
            max_hours=None, busy_dates=["2026-11-15"], description="Test fixture",
            synthetic="true", city_imputed="False", price_imputed="1"))

    def test_all_statuses_and_flags(self):
        cases = [({}, "matched"), ({"date": "2026-11-15"}, "no_eligible_candidates"),
                 ({"city": "Астана"}, "no_category_in_city"),
                 ({"budget_kzt": 1}, "no_eligible_candidates"),
                 ({"language": "казахский"}, "no_eligible_candidates")]
        for changes, status in cases:
            with self.subTest(changes=changes):
                result = safe_pipeline_call(run_pipeline, dict(self.query, **changes), [self.contractor])
                self.assertTrue(validate_output(result))
                self.assertIs(result["fallback"], False)
                self.assertEqual(result["status"], status)
                if status == "matched":
                    self.assertIsNone(result["results"][0]["max_hours"])
                    for flag in ("synthetic", "city_imputed", "price_imputed"):
                        self.assertEqual(result["results"][0][flag], self.contractor[flag])

    def test_three_card_limit(self):
        rows = [dict(self.contractor, id=f"TEST-{i}") for i in range(5)]
        result = safe_pipeline_call(run_pipeline, self.query, rows)
        self.assertFalse(result["fallback"])
        self.assertEqual(result["meta"]["returned"], 3)
        self.assertEqual(result["meta"]["eligible_candidates"], 5)


if __name__ == "__main__":
    unittest.main()
