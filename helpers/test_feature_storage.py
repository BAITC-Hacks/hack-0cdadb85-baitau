"""Feature persistence tests exclusively use temporary storage."""

import copy
import json
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from unittest.mock import patch

from . import utils


class FeatureStorageTests(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.path = Path(directory.name) / "contractors_feature.json"
        self.path.write_text("[]\n", encoding="utf-8")
        override = patch.object(utils, "_FEATURE_PATH", self.path)
        override.start()
        self.addCleanup(override.stop)
        self.contractor = dict(
            id="USR-00001", anon_name="Nova Photo", categories=["Фотограф"],
            city="Алматы", price_from_kzt=180000, event_formats=["свадьба"],
            languages=["русский"], max_hours=8, busy_dates=[],
            description="Свадебная фотография...", synthetic=True,
            city_imputed=False, price_imputed=False)

    def test_empty_storage(self):
        for content in ("[]", "", " \n"):
            self.path.write_text(content, encoding="utf-8")
            self.assertEqual(utils.load_feature_contractors(), [])
        self.path.unlink()
        self.assertEqual(utils.load_feature_contractors(), [])

    def test_first_id_and_save(self):
        self.assertEqual(utils.generate_feature_id(), "USR-00001")
        saved = utils.save_feature_contractor(self.contractor)
        self.assertEqual(saved, self.contractor)
        self.assertEqual(utils.load_feature_contractors(), [saved])

    def test_second_id_and_reload(self):
        utils.save_feature_contractor(self.contractor)
        self.assertEqual(utils.generate_feature_id(), "USR-00002")
        second = dict(self.contractor, id=utils.generate_feature_id(), anon_name="Второй фотограф")
        utils.save_feature_contractor(second)
        # Read persisted bytes independently: no in-memory ID counter or cache.
        with self.path.open(encoding="utf-8") as stream:
            self.assertEqual(json.load(stream), [self.contractor, second])
        self.assertEqual(len(utils.load_feature_contractors()), 2)
        self.assertEqual(utils.generate_feature_id(), "USR-00003")
        self.assertIn("Второй фотограф", self.path.read_text(encoding="utf-8"))

    def test_id_uses_maximum_not_count(self):
        utils.save_feature_contractor(dict(self.contractor, id="USR-00009"))
        utils.save_feature_contractor(self.contractor)
        self.assertEqual(utils.generate_feature_id(), "USR-00010")

    def test_duplicate_rejected_without_changes(self):
        utils.save_feature_contractor(self.contractor)
        original = self.path.read_bytes()
        with self.assertRaisesRegex(ValueError, "Duplicate"):
            utils.save_feature_contractor(self.contractor)
        self.assertEqual(self.path.read_bytes(), original)

    def test_invalid_submissions_rejected(self):
        changes = [dict(anon_name=" "), dict(categories=[]), dict(city=""),
                   dict(price_from_kzt=0), dict(price_from_kzt=-1), dict(price_from_kzt=True),
                   dict(event_formats=[]), dict(languages=[]), dict(description=" "),
                   dict(max_hours=0), dict(max_hours=-1), dict(max_hours=1.5), dict(max_hours=True),
                   dict(busy_dates="2026-11-14"), dict(busy_dates=["2026-02-30"]),
                   dict(busy_dates=["20261114"]), dict(id="HK-12345"), dict(id="USR-00000")]
        original = self.path.read_bytes()
        for change in changes:
            with self.subTest(change=change), self.assertRaises(ValueError):
                utils.save_feature_contractor(dict(self.contractor, **change))
        with self.assertRaises(ValueError):
            utils.save_feature_contractor({})
        self.assertEqual(self.path.read_bytes(), original)

    def test_nullable_hours_and_busy_dates(self):
        row = dict(self.contractor, max_hours=None, busy_dates=["2026-11-14"])
        utils.save_feature_contractor(row)
        self.assertEqual(utils.load_feature_contractors(), [row])

    def test_provenance_enforced_without_mutating_input(self):
        row = dict(self.contractor, synthetic=False, city_imputed=True, price_imputed=True)
        original = copy.deepcopy(row)
        saved = utils.save_feature_contractor(row)
        self.assertIs(saved["synthetic"], True)
        self.assertIs(saved["city_imputed"], False)
        self.assertIs(saved["price_imputed"], False)
        self.assertEqual(row, original)
        self.assertEqual(utils.load_feature_contractors(), [saved])

    def test_combined_catalog_preserves_base(self):
        base_path = utils._DIRECTORY / "contractors.json"
        before = base_path.read_bytes()
        base = utils.load_contractors()
        utils.save_feature_contractor(self.contractor)
        combined = utils.load_all_contractors()
        self.assertEqual(len(combined), 67)
        self.assertEqual(combined[:66], base)
        self.assertEqual(combined[-1], self.contractor)
        self.assertEqual(len(utils.load_contractors()), 66)
        self.assertEqual(base_path.read_bytes(), before)

    def test_corrupt_storage_never_overwritten(self):
        bad_rows = dict(self.contractor, synthetic=False)
        for content in ("{broken", "{}", "[null]", json.dumps([bad_rows]),
                        json.dumps([self.contractor, self.contractor])):
            self.path.write_text(content, encoding="utf-8")
            for operation in (utils.load_feature_contractors, utils.generate_feature_id,
                              lambda: utils.save_feature_contractor(self.contractor)):
                with self.subTest(content=content), self.assertRaisesRegex(ValueError, "storage is invalid"):
                    operation()
                self.assertEqual(self.path.read_text(encoding="utf-8"), content)

    def test_malformed_feature_storage_does_not_affect_base_catalog(self):
        base_path = utils._DIRECTORY / "contractors.json"
        original_bytes = base_path.read_bytes()
        original_catalog = utils.load_contractors()
        self.path.write_text("{broken", encoding="utf-8")

        with self.assertRaisesRegex(ValueError, "storage is invalid"):
            utils.load_all_contractors()

        base = utils.load_contractors()
        self.assertEqual(len(base), 66)
        self.assertEqual(base, original_catalog)
        self.assertEqual(base_path.read_bytes(), original_bytes)
        self.assertEqual(self.path.read_text(encoding="utf-8"), "{broken")

    def test_failed_write_preserves_storage(self):
        original = self.path.read_bytes()
        with patch.object(utils.os, "replace", side_effect=OSError("disk error")):
            with self.assertRaisesRegex(ValueError, "Cannot save"):
                utils.save_feature_contractor(self.contractor)
        self.assertEqual(self.path.read_bytes(), original)
        self.assertEqual(list(self.path.parent.iterdir()), [self.path])

    def test_concurrent_saves_in_one_process(self):
        rows = [dict(self.contractor, id=f"USR-{i:05d}") for i in range(1, 9)]
        with ThreadPoolExecutor(max_workers=4) as pool:
            list(pool.map(utils.save_feature_contractor, rows))
        self.assertEqual({c["id"] for c in utils.load_feature_contractors()}, {c["id"] for c in rows})


if __name__ == "__main__":
    unittest.main()
