"""Desktop interface for JarCheck with previewed, recoverable duplicate cleanup."""
from pathlib import Path
import queue
import threading
import tkinter as tk
from tkinter import filedialog, messagebox, scrolledtext, ttk

from jarcheck import VERSION, audit, duplicate_plan, quarantine_duplicates, restore_duplicates, save_report, summary


class JarCheckApp:
    def __init__(self, root):
        self.root = root
        self.report = None
        self.folder = None
        self.recovery = None
        self.results = queue.Queue()
        root.title(f"JarCheck {VERSION} — Minecraft mod folder checker")
        root.geometry("800x560")
        root.minsize(540, 410)
        tk.Label(root, text="JarCheck", font=("Segoe UI", 22, "bold")).pack(pady=(16, 4))
        self.description = tk.Label(root, text="Find identical JARs and damaged archives. Review duplicates before moving them to recovery.", wraplength=740)
        self.description.pack(padx=16)
        controls = tk.Frame(root)
        controls.pack(pady=12)
        self.scan = tk.Button(controls, text="Choose mods folder", command=self.choose, padx=8)
        self.save = tk.Button(controls, text="Save JSON report", command=self.export, state=tk.DISABLED, padx=8)
        self.copy = tk.Button(controls, text="Copy results", command=self.copy_results, state=tk.DISABLED, padx=8)
        self.cleanup = tk.Button(controls, text="Review duplicates…", command=self.review_duplicates, state=tk.DISABLED, padx=8)
        self.undo = tk.Button(controls, text="Restore recovery folder…", command=self.restore, padx=8)
        for column, widget in enumerate((self.scan, self.save, self.copy)):
            widget.grid(row=0, column=column, padx=4, pady=3)
        self.cleanup.grid(row=1, column=0, padx=4, pady=3)
        self.undo.grid(row=1, column=1, columnspan=2, padx=4, pady=3)
        self.recursive = tk.BooleanVar(value=False)
        self.recursive_toggle = tk.Checkbutton(root, text="Include subfolders (symbolic links are skipped)", variable=self.recursive)
        self.recursive_toggle.pack(pady=(0, 6))
        self.progress_text = tk.StringVar(value="Ready")
        self.progress_label = tk.Label(root, textvariable=self.progress_text, wraplength=740)
        self.progress_label.pack(padx=16)
        self.progress_bar = ttk.Progressbar(root, mode="determinate")
        self.progress_bar.pack(fill=tk.X, padx=16, pady=(4, 8))
        self.output = scrolledtext.ScrolledText(root, wrap=tk.WORD, font=("Consolas", 10))
        self.output.pack(fill=tk.BOTH, expand=True, padx=16, pady=(0, 16))
        self.display("Choose your Minecraft mods folder to begin.\n\nScanning never changes files. Duplicate cleanup only runs after you review the copies; moved files can be restored.")
        root.bind("<Configure>", self.resize)

    def resize(self, event):
        if event.widget is self.root:
            width = max(250, event.width - 40)
            self.description.configure(wraplength=width)
            self.progress_label.configure(wraplength=width)

    def display(self, text):
        self.output.configure(state=tk.NORMAL)
        self.output.delete("1.0", tk.END)
        self.output.insert(tk.END, text)
        self.output.configure(state=tk.DISABLED)

    def choose(self):
        folder = filedialog.askdirectory(title="Select Minecraft mods folder")
        if folder:
            self.start_scan(folder)

    def busy(self, value):
        mode = tk.DISABLED if value else tk.NORMAL
        for widget in (self.scan, self.recursive_toggle, self.undo):
            widget.configure(state=mode)
        if value:
            for widget in (self.save, self.copy, self.cleanup):
                widget.configure(state=tk.DISABLED)

    def start_scan(self, folder):
        self.busy(True)
        self.folder = Path(folder)
        self.report = None
        nested = self.recursive.get()
        self.display("Checking JARs…")
        self.progress_text.set("Finding JARs…")
        self.progress_bar.configure(value=0)
        def worker():
            try:
                report = audit(folder, recursive=nested, progress=lambda *event: self.results.put(("progress", event)))
                self.results.put(("done", report))
            except Exception as error:
                self.results.put(("error", str(error)))
        threading.Thread(target=worker, daemon=True).start()
        self.root.after(100, self.poll)

    def poll(self):
        try:
            kind, data = self.results.get_nowait()
            while kind == "progress":
                done, total, name = data
                self.progress_bar.configure(maximum=max(total, 1), value=done)
                self.progress_text.set(f"{done}/{total} JARs checked" + (f" — {name}" if name else ""))
                kind, data = self.results.get_nowait()
        except queue.Empty:
            self.root.after(100, self.poll)
            return
        self.busy(False)
        if kind == "error":
            self.progress_text.set("Scan failed")
            self.display("Could not complete scan: " + data)
            return
        self.report = data
        self.display(summary(data))
        self.progress_text.set(f"Finished — {len(data['files'])} JARs checked")
        self.save.configure(state=tk.NORMAL)
        self.copy.configure(state=tk.NORMAL)
        self.cleanup.configure(state=tk.NORMAL if duplicate_plan(data) else tk.DISABLED)

    def export(self):
        path = filedialog.asksaveasfilename(defaultextension=".json", initialfile="jarcheck-report.json", filetypes=[("JSON report", "*.json")])
        if path:
            try:
                save_report(self.report, path)
            except (ValueError, OSError) as error:
                messagebox.showerror("Save failed", str(error))

    def copy_results(self):
        self.root.clipboard_clear()
        self.root.clipboard_append(summary(self.report))
        self.progress_text.set("Results copied to clipboard")

    def run_operation(self, task, title, success):
        self.busy(True)
        self.progress_text.set(title)
        self.progress_bar.configure(mode="indeterminate")
        self.progress_bar.start()
        result_queue = queue.Queue()
        def worker():
            try:
                result_queue.put((True, task()))
            except Exception as error:
                result_queue.put((False, str(error)))
        def finished():
            try:
                ok, data = result_queue.get_nowait()
            except queue.Empty:
                self.root.after(100, finished)
                return
            self.progress_bar.stop()
            self.progress_bar.configure(mode="determinate", value=0)
            self.busy(False)
            if ok:
                success(data)
            else:
                messagebox.showerror(title + " stopped", data)
            if self.folder:
                self.start_scan(self.folder)
        threading.Thread(target=worker, daemon=True).start()
        self.root.after(100, finished)

    def review_duplicates(self):
        plans = duplicate_plan(self.report)
        if not plans:
            return
        window = tk.Toplevel(self.root)
        window.title("Review identical copies")
        window.geometry("680x420")
        window.transient(self.root)
        window.grab_set()
        tk.Label(window, text="Choose one JAR to keep in each group. Extra copies go to a sibling\nJarCheck-Recovery folder. Damaged or unchecked files are not moved.", wraplength=640).pack(padx=16, pady=12)
        area = tk.Frame(window)
        area.pack(fill=tk.BOTH, expand=True, padx=16)
        canvas = tk.Canvas(area, highlightthickness=0)
        scroll = ttk.Scrollbar(area, orient=tk.VERTICAL, command=canvas.yview)
        canvas.configure(yscrollcommand=scroll.set)
        scroll.pack(side=tk.RIGHT, fill=tk.Y)
        canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        fields = tk.Frame(canvas)
        canvas.create_window((0, 0), window=fields, anchor="nw")
        fields.bind("<Configure>", lambda event: canvas.configure(scrollregion=canvas.bbox("all")))
        choices = []
        for index, plan in enumerate(plans, 1):
            tk.Label(fields, text=f"Group {index}: {len(plan['remove'])} extra copy/copies — keep:").pack(anchor="w", pady=(8, 2))
            choice = ttk.Combobox(fields, values=[plan["keep"], *plan["remove"]], state="readonly", width=68)
            choice.set(plan["keep"])
            choice.pack(anchor="w", pady=(0, 6))
            choices.append(choice)
        actions = tk.Frame(window)
        actions.pack(pady=12)
        def move():
            keepers = [choice.get() for choice in choices]
            count = sum(len(plan["remove"]) for plan in plans)
            if not messagebox.askyesno("Move duplicate JARs?", f"Keep your selected copies and move {count} extra JAR(s) to recovery? Close Minecraft and your launcher first.", parent=window):
                return
            report, folder = self.report, self.folder
            window.destroy()
            def success(result):
                self.recovery = result["recovery_folder"]
                messagebox.showinfo("Duplicates moved", f"Moved {len(result['moved'])} extra copy/copies.\nRecovery folder:\n{self.recovery}\n\nUse Restore recovery folder to undo this cleanup.")
            self.run_operation(lambda: quarantine_duplicates(folder, report, keepers), "Moving duplicates", success)
        tk.Button(actions, text="Move extra copies to recovery", command=move).pack(side=tk.LEFT, padx=6)
        tk.Button(actions, text="Cancel", command=window.destroy).pack(side=tk.LEFT, padx=6)

    def restore(self):
        folder = filedialog.askdirectory(title="Choose a folder containing recovery.json", initialdir=self.recovery or str(Path.home()))
        if not folder:
            return
        if not messagebox.askyesno("Restore recovered JARs?", "Restore moved JARs to their original folder? Existing files will never be overwritten."):
            return
        self.run_operation(lambda: restore_duplicates(folder), "Restoring JARs", lambda restored: messagebox.showinfo("Restored", f"Restored {len(restored)} JAR file(s)."))


def main():
    root = tk.Tk()
    JarCheckApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
