import hashlib
import json
import shutil
import subprocess
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest.mock import patch

from jarcheck import audit, save_report, summary


class AuditTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.folder = Path(self.temp.name)

    def jar(self, name, content=b"hello"):
        path = self.folder / name
        with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_STORED) as archive:
            archive.writestr("payload.txt", content)
        return path

    def test_identical_renamed_files_and_read_only(self):
        first = self.jar("a.jar")
        shutil.copyfile(first, self.folder / "renamed.JAR")
        before = {p.name: p.read_bytes() for p in self.folder.iterdir()}
        self.assertEqual(audit(self.folder)["identical_groups"], [["a.jar", "renamed.JAR"]])
        self.assertEqual(before, {p.name: p.read_bytes() for p in self.folder.iterdir()})

    def test_distinct_jars(self):
        self.jar("a.jar", b"a")
        self.jar("b.jar", b"b")
        self.assertEqual(audit(self.folder)["identical_groups"], [])

    def test_changing_file_not_reported_as_identical(self):
        first = self.jar("a.jar")
        shutil.copyfile(first, self.folder / "b.jar")
        real_digest = hashlib.file_digest

        def digest_then_change(stream, algorithm):
            result = real_digest(stream, algorithm)
            if Path(stream.name).name == "a.jar":
                with first.open("ab") as target:
                    target.write(b"changed during scan")
            return result

        with patch("jarcheck.hashlib.file_digest", side_effect=digest_then_change):
            report = audit(self.folder)
        self.assertEqual(report["files"][0]["status"], "changed")
        self.assertNotIn("sha256", report["files"][0])
        self.assertEqual(report["identical_groups"], [])

    def test_invalid_and_crc_damaged(self):
        (self.folder / "invalid.jar").write_bytes(b"not a ZIP")
        damaged = self.jar("damaged.jar", b"unique-payload")
        damaged.write_bytes(damaged.read_bytes().replace(b"unique-payload", b"broken-payload"))
        records = {r["name"]: r for r in audit(self.folder)["files"]}
        self.assertEqual(records["invalid.jar"]["status"], "invalid")
        self.assertEqual(records["damaged.jar"]["status"], "damaged")

    def test_limits_skip_validation(self):
        self.jar("big.jar", b"1234")
        with patch("jarcheck.MAX_UNPACKED_BYTES", 2):
            self.assertEqual(audit(self.folder)["files"][0]["status"], "unchecked")

    def test_non_jars_and_nested_folders_ignored(self):
        (self.folder / "notes.txt").write_text("hello")
        (self.folder / "nested.jar").mkdir()
        self.assertEqual(audit(self.folder)["files"], [])
        self.assertIn("0 JAR", summary(audit(self.folder)))
        self.assertIn("No JAR files found", summary(audit(self.folder)))

    def test_progress_counts_nested_invalid_and_duplicate_files(self):
        self.jar("a.jar")
        (self.folder / "nested").mkdir()
        (self.folder / "nested" / "bad.jar").write_bytes(b"bad")
        events = []
        report = audit(self.folder, recursive=True, progress=lambda *event: events.append(event))
        self.assertEqual(len(report["files"]), 2)
        self.assertEqual(events, [(0, 2, "a.jar"), (1, 2, "nested/bad.jar"), (2, 2, "")])

    def test_empty_folder_progress_completes(self):
        events = []
        audit(self.folder, progress=lambda *event: events.append(event))
        self.assertEqual(events, [(0, 0, "")])

    def test_missing_folder(self):
        with self.assertRaises(ValueError):
            audit(self.folder / "missing")

    def test_recursive_uses_relative_paths_and_is_opt_in(self):
        first = self.jar("a.jar")
        nested = self.folder / "nested"
        nested.mkdir()
        shutil.copyfile(first, nested / "renamed.jar")
        self.assertEqual(len(audit(self.folder)["files"]), 1)
        report = audit(self.folder, recursive=True)
        self.assertEqual(report["identical_groups"], [["a.jar", "nested/renamed.jar"]])
        self.assertTrue(report["recursive"])

    def test_symbolic_links_are_not_followed(self):
        with tempfile.TemporaryDirectory() as outside:
            target = Path(outside) / "external.jar"
            target.write_bytes(b"not an archive")
            try:
                (self.folder / "link.jar").symlink_to(target)
                (self.folder / "directory").symlink_to(outside, target_is_directory=True)
            except OSError:
                self.skipTest("Symbolic link creation is unavailable")
            report = audit(self.folder, recursive=True)
            self.assertEqual(report["files"], [{"name": "link.jar", "status": "skipped", "detail": "Symbolic links are not scanned."}])

    def test_safe_report_export_and_failed_write_preserves_previous_report(self):
        jar = self.jar("a.jar")
        original = jar.read_bytes()
        report = audit(self.folder)
        with self.assertRaises(ValueError):
            save_report(report, jar)
        self.assertEqual(jar.read_bytes(), original)
        output = self.folder / "report.json"
        save_report(report, output)
        self.assertEqual(json.loads(output.read_text()), report)
        before = output.read_bytes()
        with patch("jarcheck.json.dump", side_effect=ValueError("cannot encode")):
            with self.assertRaises(ValueError):
                save_report(report, output)
        self.assertEqual(output.read_bytes(), before)
        self.assertEqual(list(self.folder.glob(".jarcheck-*.tmp")), [])

    def test_report_output_rejects_symbolic_link(self):
        target = self.folder / "target.jar"
        target.write_bytes(b"original")
        link = self.folder / "report.json"
        try:
            link.symlink_to(target)
        except OSError:
            self.skipTest("Symbolic link creation is unavailable")
        with self.assertRaises(ValueError):
            save_report(audit(self.folder), link)
        self.assertEqual(target.read_bytes(), b"original")

    def test_cli_recursive_and_output(self):
        self.jar("a.jar")
        (self.folder / "nested").mkdir()
        shutil.copyfile(self.folder / "a.jar", self.folder / "nested" / "b.jar")
        script = Path(__file__).resolve().parents[1] / "jarcheck.py"
        output = self.folder / "report.json"
        command = [sys.executable, str(script), str(self.folder), "--recursive", "--output", str(output)]
        result = subprocess.run(command, capture_output=True, text=True)
        self.assertEqual(result.returncode, 1)
        self.assertEqual(json.loads(output.read_text())["identical_groups"], [["a.jar", "nested/b.jar"]])

    def test_cli_json_and_exit_codes(self):
        script = Path(__file__).resolve().parents[1] / "jarcheck.py"
        self.jar("a.jar")
        command = [sys.executable, str(script), str(self.folder), "--json"]
        result = subprocess.run(command, capture_output=True, text=True)
        self.assertEqual(result.returncode, 0)
        self.assertEqual(json.loads(result.stdout)["files"][0]["status"], "ok")
        shutil.copyfile(self.folder / "a.jar", self.folder / "b.jar")
        self.assertEqual(subprocess.run(command, capture_output=True).returncode, 1)


if __name__ == "__main__":
    unittest.main()
