"""Run with: PYTHONDONTWRITEBYTECODE=1 python -m unittest helpers.test_utils -v"""

import copy
import json
import tempfile
import threading
import unittest
from pathlib import Path
from unittest.mock import patch

from . import utils
from .prepare_data import build_mock, read_source


class UtilitiesTests(unittest.TestCase):
    def setUp(self):
        # Explicit test fixture, never included in the runtime catalog.
        self.raw = dict(id="TEST-ONLY", anon_name="Тестовый профиль", city="Алматы",
                        categories="['Фотограф', 'Видеограф']", price_from_kzt="300 000 ₸",
                        event_formats='["свадьба"]', languages=["русский"], max_hours="10.0",
                        busy_dates="['14.11.2026', '2026-10-03']", description="Test fixture",
                        synthetic="False", city_imputed="0", price_imputed="True")
        self.contractor = utils.normalize_contractor(self.raw)
        self.request = dict(city="Алматы", date="2026-11-15", event_format="свадьба",
                            category="Фотограф", budget_kzt=400000, duration_hours=8, language="русский")
        self.mock = build_mock([self.contractor])

    def test_lists_and_booleans(self):
        for value in (None, float("nan"), "", "NaN"):
            self.assertEqual(utils.parse_list_field(value), [])
        for value in (["a"], '["a"]', "['a']", "a"):
            self.assertEqual(utils.parse_list_field(value), ["a"])
        for value in ('{"a": 1}', "('a',)", "[bad", 5):
            with self.assertRaises(ValueError):
                utils.parse_list_field(value)
        for value in (False, "false", "False", 0, "0", None):
            self.assertIs(utils.parse_bool(value), False)
        for value in (True, "true", "True", 1, "1"):
            self.assertIs(utils.parse_bool(value), True)

    def test_normalization_preserves_data(self):
        self.assertEqual(self.contractor["busy_dates"], ["2026-11-14", "2026-10-03"])
        self.assertEqual(self.contractor["price_from_kzt"], 300000)
        self.assertIs(self.contractor["synthetic"], False)
        self.assertIs(self.contractor["price_imputed"], True)
        self.assertTrue(utils.validate_contractor(self.contractor))
        nullable = utils.normalize_contractor(dict(self.raw, max_hours=None))
        self.assertIsNone(nullable["max_hours"])
        for field, value in (("price_from_kzt", None), ("city", ""), ("busy_dates", '["2026-02-30"]'),
                             ("price_from_kzt", True), ("price_from_kzt", 1.5)):
            with self.assertRaises(ValueError):
                utils.normalize_contractor(dict(self.raw, **{field: value}))

    def test_optional_request_fields(self):
        request = {k: v for k, v in self.request.items() if k not in {"language", "duration_hours"}}
        normalized = utils.normalize_request(request)
        self.assertIsNone(normalized["language"])
        self.assertIsNone(normalized["duration_hours"])
        for changes in ({"date": "2026-02-30"}, {"duration_hours": float("inf")}, {"budget_kzt": -1}, {"budget_kzt": 0}):
            with self.assertRaises(ValueError):
                utils.normalize_request(dict(request, **changes))

    def test_mock_eligibility(self):
        self.assertTrue(utils.validate_output(self.mock))
        self.assertNotIn(self.mock["query"]["date"], self.contractor["busy_dates"])
        self.assertEqual(self.mock["results"][0]["id"], self.contractor["id"])
        for changes in ({"city": "Астана"}, {"price_from_kzt": 500000}, {"max_hours": 7},
                        {"languages": ["казахский"]}, {"event_formats": ["юбилей"]}, {"categories": ["Флорист"]}):
            with self.assertRaises(ValueError):
                build_mock([dict(self.contractor, **changes)])

    def test_malformed_output(self):
        for value in (None, [], {}, dict(self.mock, status=[]), dict(self.mock, results=[]),
                      dict(self.mock, results=self.mock["results"] * 4), dict(self.mock, meta={})):
            self.assertFalse(utils.validate_output(value))
        for changes in ({"explanation": " "}, {"price_from_kzt": "300000"}, {"score": float("nan")},
                        {"synthetic": "false"}, {"max_hours": False}):
            result = copy.deepcopy(self.mock)
            result["results"][0].update(changes)
            self.assertFalse(utils.validate_output(result))

    def test_core_and_fallback(self):
        with tempfile.TemporaryDirectory() as temp:
            folder = Path(temp)
            (folder / "mock_data.json").write_text(json.dumps(self.mock), encoding="utf-8")
            with patch.object(utils, "_DIRECTORY", folder):
                def broken(*args):
                    raise RuntimeError("LLM unavailable")

                for pipeline in (broken, lambda *args: None, lambda *args: {"status": "matched"}):
                    result = utils.safe_pipeline_call(pipeline, self.request, [self.contractor])
                    self.assertEqual(result["status"], "matched")
                    self.assertIs(result["fallback"], True)
                result = utils.safe_pipeline_call(lambda *args: self.mock, self.request, [self.contractor])
                self.assertIs(result["fallback"], False)
                self.assertIs(self.mock["fallback"], True)
                result = utils.safe_pipeline_call(broken, {}, [self.contractor])
                self.assertTrue(utils.validate_output(result))
                (folder / "mock_data.json").write_text("{broken", encoding="utf-8")
                self.assertTrue(utils.validate_output(utils.load_mock_data()))
                (folder / "mock_data.json").unlink()
                self.assertTrue(utils.validate_output(utils.load_mock_data()))

    def test_timeout_and_worker_capacity(self):
        release = threading.Event()
        done = threading.Event()

        def hanging(query, contractors):
            release.wait(2)
            contractors[0]["city"] = "mutated"
            done.set()
            return self.mock

        slots = threading.BoundedSemaphore(1)
        with patch.object(utils, "_CORE_SLOTS", slots):
            try:
                result = utils.safe_pipeline_call(hanging, self.request, [self.contractor], timeout_seconds=0.01)
                self.assertIs(result["fallback"], True)
                self.assertFalse(slots.acquire(blocking=False))
                called = []
                result = utils.safe_pipeline_call(lambda *args: called.append(True), self.request, [self.contractor])
                self.assertIs(result["fallback"], True)
                self.assertEqual(called, [])
            finally:
                release.set()
                self.assertTrue(done.wait(1))
                self.assertTrue(slots.acquire(timeout=1))
                slots.release()
        self.assertEqual(self.contractor["city"], "Алматы")

    def test_load_catalog_and_source_formats(self):
        with tempfile.TemporaryDirectory() as temp:
            folder = Path(temp)
            rows = [dict(self.contractor, id=f"TEST-{i}") for i in range(66)]
            target = folder / "contractors.json"
            target.write_text(json.dumps(rows), encoding="utf-8")
            with patch.object(utils, "_DIRECTORY", folder):
                self.assertEqual(len(utils.load_contractors()), 66)
                rows[-1]["id"] = rows[0]["id"]
                target.write_text(json.dumps(rows), encoding="utf-8")
                with self.assertRaises(ValueError):
                    utils.load_contractors()
                target.write_text("[]", encoding="utf-8")
                with self.assertRaises(ValueError):
                    utils.load_contractors()
            for suffix in ("json", "jsonl", "csv"):
                source = folder / f"source.{suffix}"
                if suffix == "csv":
                    import csv
                    with source.open("w", encoding="utf-8-sig", newline="") as output:
                        writer = csv.DictWriter(output, fieldnames=self.raw.keys())
                        writer.writeheader()
                        writer.writerow(self.raw)
                else:
                    source.write_text(json.dumps([self.raw] if suffix == "json" else self.raw), encoding="utf-8")
                self.assertEqual(utils.normalize_contractor(read_source(source)[0]), self.contractor)


if __name__ == "__main__":
    unittest.main()
