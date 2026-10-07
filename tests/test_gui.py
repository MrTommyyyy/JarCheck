"""Exercise actual Tk widgets; native file/dialog responses use disposable inputs.

Windows CI runs these. On another desktop set JARCHECK_GUI_TESTS=1 explicitly;
hosted macOS runners can crash in native Tk modal-window code.
"""
import json
import os
import shutil
import tempfile
import sys
import time
import tkinter as tk
import unittest
import zipfile
from pathlib import Path
from unittest.mock import patch

from gui import JarCheckApp
from jarcheck import VERSION


@unittest.skipUnless(sys.platform == "win32" or os.environ.get("JARCHECK_GUI_TESTS") == "1", "Desktop checks run on Windows; use JARCHECK_GUI_TESTS=1 on another desktop")
class DesktopTests(unittest.TestCase):
    def setUp(self):
        try:
            self.root = tk.Tk()
        except tk.TclError as error:
            self.skipTest("No Tk display: " + str(error))
        self.addCleanup(self.root.destroy)
        self.app = JarCheckApp(self.root)
        self.root.update()
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.folder = Path(self.temp.name) / "mods"
        self.folder.mkdir()
        with zipfile.ZipFile(self.folder / "first.jar", "w") as archive:
            archive.writestr("payload.txt", "synthetic")
        self.errors = []
        self.addCleanup(patch.stopall)
        patch("gui.messagebox.showerror", side_effect=lambda *args, **kwargs: self.errors.append(args)).start()
        patch("gui.messagebox.showinfo").start()

    def wait_for(self, predicate):
        deadline = time.monotonic() + 10
        while time.monotonic() < deadline:
            self.root.update()
            if predicate():
                return
            time.sleep(0.01)
        self.fail("Desktop action did not finish within ten seconds")

    def scan(self):
        with patch("gui.filedialog.askdirectory", return_value=str(self.folder)):
            self.app.scan.invoke()
        self.wait_for(lambda: self.app.report is not None)

    def children(self, widget):
        for child in widget.winfo_children():
            yield child
            yield from self.children(child)

    def test_startup_cancel_and_resize(self):
        self.assertIn(VERSION, self.root.title())
        self.assertEqual(str(self.app.save["state"]), "disabled")
        self.assertEqual(str(self.app.cleanup["state"]), "disabled")
        with patch("gui.filedialog.askdirectory", return_value=""):
            self.app.scan.invoke()
        self.assertIsNone(self.app.report)
        self.root.geometry("540x410")
        self.root.update()
        self.assertLessEqual(self.app.description["wraplength"], 500)
        for button in (self.app.scan, self.app.save, self.app.copy, self.app.cleanup, self.app.undo):
            self.assertLessEqual(button.winfo_rootx() + button.winfo_width(), self.root.winfo_rootx() + self.root.winfo_width())

    def test_scan_nested_copy_clipboard_and_export(self):
        nested = self.folder / "nested"
        nested.mkdir()
        shutil.copyfile(self.folder / "first.jar", nested / "copy.jar")
        (self.folder / "bad.jar").write_bytes(b"not an archive")
        self.app.recursive_toggle.invoke()
        self.scan()
        self.assertEqual(len(self.app.report["files"]), 3)
        self.assertEqual(self.app.report["identical_groups"], [["first.jar", "nested/copy.jar"]])
        self.assertEqual(float(self.app.progress_bar["value"]), 3)
        self.app.copy.invoke()
        self.assertIn("INVALID: bad.jar", self.root.clipboard_get())
        output = self.folder.parent / "report.json"
        with patch("gui.filedialog.asksaveasfilename", return_value=str(output)):
            self.app.save.invoke()
        self.assertEqual(json.loads(output.read_text()), self.app.report)
        before = (self.folder / "first.jar").read_bytes()
        with patch("gui.filedialog.asksaveasfilename", return_value=str(self.folder / "first.jar")):
            self.app.save.invoke()
        self.assertEqual(len(self.errors), 1)
        self.assertEqual((self.folder / "first.jar").read_bytes(), before)

    def test_review_cancel_choose_keeper_move_rescan_and_restore(self):
        shutil.copyfile(self.folder / "first.jar", self.folder / "copy.jar")
        self.scan()
        self.app.cleanup.invoke()
        review = next(w for w in self.root.winfo_children() if isinstance(w, tk.Toplevel))
        next(w for w in self.children(review) if isinstance(w, tk.Button) and w["text"] == "Cancel").invoke()
        self.assertTrue((self.folder / "copy.jar").exists())
        self.app.cleanup.invoke()
        review = next(w for w in self.root.winfo_children() if isinstance(w, tk.Toplevel))
        from tkinter import ttk
        next(w for w in self.children(review) if isinstance(w, ttk.Combobox)).set("first.jar")
        move = next(w for w in self.children(review) if isinstance(w, tk.Button) and w["text"] == "Move extra copies to recovery")
        with patch("gui.messagebox.askyesno", return_value=True):
            move.invoke()
        self.wait_for(lambda: self.app.recovery is not None and self.app.report is not None and not self.app.report["identical_groups"])
        self.assertTrue((self.folder / "first.jar").exists())
        self.assertFalse((self.folder / "copy.jar").exists())
        self.assertEqual(str(self.app.cleanup["state"]), "disabled")
        with patch("gui.filedialog.askdirectory", return_value=self.app.recovery), patch("gui.messagebox.askyesno", return_value=True):
            self.app.undo.invoke()
        self.wait_for(lambda: self.app.report is not None and bool(self.app.report["identical_groups"]))
        self.assertTrue((self.folder / "copy.jar").exists())
        self.assertEqual(self.errors, [])

    def test_missing_folder_failure_then_recover(self):
        with patch("gui.filedialog.askdirectory", return_value=str(self.folder / "missing")):
            self.app.scan.invoke()
        self.wait_for(lambda: str(self.app.scan["state"]) == "normal")
        self.assertIn("Could not complete scan", self.app.output.get("1.0", tk.END))
        self.assertEqual(str(self.app.save["state"]), "disabled")
        self.scan()
        self.assertEqual(self.app.report["files"][0]["status"], "ok")


if __name__ == "__main__":
    unittest.main()
