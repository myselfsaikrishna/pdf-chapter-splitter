import json
import tempfile
import unittest
from pathlib import Path

from audit import audit_manifest


class AuditManifestTests(unittest.TestCase):
    def write_manifest(self, directory, chapters, page_count=100):
        path = Path(directory) / "chapters.json"
        path.write_text(json.dumps({"page_count": page_count, "chapters": chapters}), encoding="utf-8")
        return str(path)

    def test_contiguous_chapters_pass(self):
        with tempfile.TemporaryDirectory() as directory:
            manifest = self.write_manifest(directory, [
                {"chapter_number": 1, "title": "Intro", "start_page": 1, "end_page": 10},
                {"chapter_number": 2, "title": "Methods", "start_page": 11, "end_page": 20},
            ])
            report = audit_manifest(manifest)
            self.assertTrue(report["passed"])
            self.assertEqual(report["errors"], [])
            self.assertFalse(any("Gap" in warning for warning in report["warnings"]))

    def test_overlap_is_error(self):
        with tempfile.TemporaryDirectory() as directory:
            manifest = self.write_manifest(directory, [
                {"title": "One", "start_page": 1, "end_page": 12},
                {"title": "Two", "start_page": 11, "end_page": 20},
            ])
            report = audit_manifest(manifest)
            self.assertFalse(report["passed"])
            self.assertTrue(any("Overlap" in error for error in report["errors"]))

    def test_gap_is_reported_as_warning(self):
        with tempfile.TemporaryDirectory() as directory:
            manifest = self.write_manifest(directory, [
                {"title": "One", "start_page": 1, "end_page": 8},
                {"title": "Two", "start_page": 11, "end_page": 20},
            ])
            report = audit_manifest(manifest)
            self.assertTrue(report["passed"])
            self.assertTrue(any("Gap" in warning for warning in report["warnings"]))

    def test_duplicate_chapter_number_is_error(self):
        with tempfile.TemporaryDirectory() as directory:
            manifest = self.write_manifest(directory, [
                {"chapter_number": 1, "title": "One", "start_page": 1, "end_page": 10},
                {"chapter_number": 1, "title": "Two", "start_page": 11, "end_page": 20},
            ])
            report = audit_manifest(manifest)
            self.assertFalse(report["passed"])
            self.assertTrue(any("Duplicate chapter_number" in error for error in report["errors"]))

    def test_page_out_of_range_is_error(self):
        with tempfile.TemporaryDirectory() as directory:
            manifest = self.write_manifest(directory, [
                {"title": "One", "start_page": 101, "end_page": 110},
            ], page_count=100)
            report = audit_manifest(manifest)
            self.assertFalse(report["passed"])
            self.assertTrue(any("beyond PDF page count" in error for error in report["errors"]))

    def test_missing_final_end_is_warning(self):
        with tempfile.TemporaryDirectory() as directory:
            manifest = self.write_manifest(directory, [
                {"title": "One", "start_page": 1, "end_page": 10},
                {"title": "Two", "start_page": 11, "end_page": None},
            ])
            report = audit_manifest(manifest, last_end_page=20)
            self.assertTrue(report["passed"])
            self.assertFalse(any("Final chapter" in warning for warning in report["warnings"]))


if __name__ == "__main__":
    unittest.main()
