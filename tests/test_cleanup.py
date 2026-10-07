import json
import shutil
import subprocess
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest.mock import patch

from jarcheck import audit, duplicate_plan, quarantine_duplicates, restore_duplicates


class CleanupTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.parent = Path(self.temp.name)
        self.folder = self.parent / "mods"
        self.folder.mkdir()
        with zipfile.ZipFile(self.folder / "a.jar", "w") as archive:
            archive.writestr("test.txt", "synthetic archive")
        shutil.copyfile(self.folder / "a.jar", self.folder / "b.jar")

    def test_selected_keeper_recovery_and_idempotent_restore(self):
        original = {p.name: p.read_bytes() for p in self.folder.iterdir()}
        result = quarantine_duplicates(self.folder, audit(self.folder), ["b.jar"])
        self.assertEqual(result["moved"], ["a.jar"])
        self.assertEqual(sorted(p.name for p in self.folder.iterdir()), ["b.jar"])
        recovery = Path(result["recovery_folder"])
        self.assertEqual(recovery.parent, self.parent.resolve() / "JarCheck-Recovery")
        self.assertEqual((recovery / "a.jar").read_bytes(), original["a.jar"])
        self.assertEqual(restore_duplicates(recovery), ["a.jar"])
        self.assertEqual(original, {p.name: p.read_bytes() for p in self.folder.iterdir()})
        self.assertEqual(restore_duplicates(recovery), [])

    def test_nested_copy_and_distinct_file_preserved(self):
        nested = self.folder / "nested"
        nested.mkdir()
        (self.folder / "b.jar").rename(nested / "b.jar")
        with zipfile.ZipFile(self.folder / "unique.jar", "w") as archive:
            archive.writestr("different.txt", "different")
        before = (self.folder / "unique.jar").read_bytes()
        result = quarantine_duplicates(self.folder, audit(self.folder, recursive=True))
        self.assertEqual(result["moved"], ["nested/b.jar"])
        self.assertEqual((self.folder / "unique.jar").read_bytes(), before)
        self.assertEqual(restore_duplicates(result["recovery_folder"]), ["nested/b.jar"])

    def test_changed_keeper_or_extra_refuses_before_any_move(self):
        for name in ("a.jar", "b.jar"):
            with self.subTest(name=name):
                report = audit(self.folder)
                path = self.folder / name
                before = path.read_bytes()
                path.write_bytes(before + b"changed")
                with self.assertRaisesRegex(ValueError, "changed"):
                    quarantine_duplicates(self.folder, report)
                self.assertTrue((self.folder / "a.jar").exists())
                self.assertTrue((self.folder / "b.jar").exists())
                self.assertFalse((self.parent / "JarCheck-Recovery").exists())
                path.write_bytes(before)

    def test_damaged_and_unchecked_groups_are_not_moved(self):
        report = audit(self.folder)
        for status in ("invalid", "damaged", "unchecked", "changed"):
            report["files"][0]["status"] = status
            self.assertEqual(duplicate_plan(report), [])
            self.assertEqual(quarantine_duplicates(self.folder, report)["moved"], [])

    def test_restore_refuses_existing_target_and_tampered_backup(self):
        result = quarantine_duplicates(self.folder, audit(self.folder))
        recovery = Path(result["recovery_folder"])
        target = self.folder / "b.jar"
        target.write_bytes(b"new user file")
        with self.assertRaisesRegex(ValueError, "overwrite"):
            restore_duplicates(recovery)
        self.assertEqual(target.read_bytes(), b"new user file")
        self.assertTrue((recovery / "b.jar").exists())
        target.unlink()
        (recovery / "b.jar").write_bytes(b"tampered")
        with self.assertRaisesRegex(ValueError, "changed"):
            restore_duplicates(recovery)
        self.assertFalse(target.exists())

    def test_untrusted_recovery_paths_and_malformed_records_rejected(self):
        result = quarantine_duplicates(self.folder, audit(self.folder))
        manifest_path = Path(result["recovery_folder"]) / "recovery.json"
        original = json.loads(manifest_path.read_text())
        for name in ("../outside.jar", "/outside.jar", "C:/outside.jar", "nested\\outside.jar", "a/./b.jar"):
            original["moves"][0]["name"] = name
            manifest_path.write_text(json.dumps(original))
            with self.assertRaises(ValueError):
                restore_duplicates(result["recovery_folder"])
        for malformed in ([], {"format": "jarcheck-recovery/v1", "source_folder": str(self.folder), "moves": [42]}):
            manifest_path.write_text(json.dumps(malformed))
            with self.assertRaises(ValueError):
                restore_duplicates(result["recovery_folder"])

    def test_symbolic_link_replacement_rejected(self):
        report = audit(self.folder)
        extra = self.folder / "b.jar"
        extra.unlink()
        try:
            extra.symlink_to(self.folder / "a.jar")
        except OSError:
            self.skipTest("Symbolic links unavailable")
        with self.assertRaisesRegex(ValueError, "Symbolic"):
            quarantine_duplicates(self.folder, report)
        self.assertTrue((self.folder / "a.jar").exists())

    def test_partial_move_failure_can_restore_using_preserved_record(self):
        shutil.copyfile(self.folder / "a.jar", self.folder / "c.jar")
        real_rename = Path.rename
        def fail_second(source, target):
            if source.name == "c.jar":
                raise OSError("simulated interruption")
            return real_rename(source, target)
        with patch("pathlib.Path.rename", fail_second):
            with self.assertRaisesRegex(ValueError, "1 file.*recovery record"):
                quarantine_duplicates(self.folder, audit(self.folder))
        recovery = next((self.parent / "JarCheck-Recovery").iterdir())
        self.assertTrue((self.folder / "a.jar").exists())
        self.assertTrue((self.folder / "c.jar").exists())
        self.assertEqual(restore_duplicates(recovery), ["b.jar"])

    def test_cli_scan_read_only_then_explicit_cleanup_and_restore(self):
        script = Path(__file__).resolve().parents[1] / "jarcheck.py"
        def run(*args):
            return subprocess.run([sys.executable, str(script), *map(str, args)], capture_output=True, text=True)
        self.assertEqual(run(self.folder).returncode, 1)
        self.assertTrue((self.folder / "b.jar").exists())
        cleaned = run(self.folder, "--quarantine-duplicates", "--json")
        self.assertEqual(cleaned.returncode, 0, cleaned.stderr)
        report = json.loads(cleaned.stdout)
        self.assertEqual(report["cleanup"]["moved"], ["b.jar"])
        self.assertEqual(run("--restore", report["cleanup"]["recovery_folder"]).returncode, 0)
        self.assertTrue((self.folder / "b.jar").exists())


if __name__ == "__main__":
    unittest.main()
