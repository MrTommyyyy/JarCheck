"""Desktop interface for JarCheck; no network access or third-party packages."""
import queue
import threading
import tkinter as tk
from tkinter import filedialog, messagebox, scrolledtext, ttk

from jarcheck import VERSION, audit, save_report, summary


def main():
    root = tk.Tk()
    root.title(f"JarCheck {VERSION} — Minecraft mod folder checker")
    root.geometry("780x500")
    root.minsize(540, 340)
    tk.Label(root, text="JarCheck", font=("Segoe UI", 22, "bold")).pack(pady=(16, 4))
    tk.Label(root, text="Find identical JARs and damaged archives. Your files stay on your computer.").pack(padx=12)
    controls = tk.Frame(root)
    controls.pack(pady=12)
    recursive = tk.BooleanVar(value=False)
    recursive_toggle = tk.Checkbutton(root, text="Include subfolders (symbolic links are skipped)", variable=recursive)
    recursive_toggle.pack(pady=(0, 8))
    progress_text = tk.StringVar(value="Ready")
    tk.Label(root, textvariable=progress_text).pack()
    progress_bar = ttk.Progressbar(root, mode="determinate")
    progress_bar.pack(fill=tk.X, padx=16, pady=(4, 8))
    output = scrolledtext.ScrolledText(root, wrap=tk.WORD, font=("Consolas", 10))
    output.pack(fill=tk.BOTH, expand=True, padx=16, pady=(0, 16))
    output.insert(tk.END, "Choose your Minecraft mods folder to begin.\n\nNo files are changed or deleted.")
    output.configure(state=tk.DISABLED)
    results = queue.Queue()
    state = {"report": None}

    def display(text):
        output.configure(state=tk.NORMAL)
        output.delete("1.0", tk.END)
        output.insert(tk.END, text)
        output.configure(state=tk.DISABLED)

    def choose():
        folder = filedialog.askdirectory(title="Select Minecraft mods folder")
        if not folder:
            return
        scan.configure(state=tk.DISABLED)
        save.configure(state=tk.DISABLED)
        copy.configure(state=tk.DISABLED)
        recursive_toggle.configure(state=tk.DISABLED)
        include_nested = recursive.get()
        state["report"] = None
        display("Checking JARs…")
        progress_text.set("Finding JARs…")
        progress_bar.configure(value=0)

        def worker():
            try:
                results.put(("done", audit(folder, recursive=include_nested, progress=lambda done, total, name: results.put(("progress", (done, total, name))))))
            except Exception as exc:
                results.put(("error", str(exc)))
        threading.Thread(target=worker, daemon=True).start()
        root.after(100, poll)

    def poll():
        try:
            kind, data = results.get_nowait()
            while kind == "progress":
                done, total, name = data
                progress_bar.configure(maximum=max(total, 1), value=done)
                progress_text.set(f"{done}/{total} JARs checked" + (f" — {name}" if name else ""))
                kind, data = results.get_nowait()
        except queue.Empty:
            root.after(100, poll)
            return
        scan.configure(state=tk.NORMAL)
        recursive_toggle.configure(state=tk.NORMAL)
        if kind == "error":
            progress_text.set("Scan failed")
            display("Could not complete scan: " + data)
            return
        state["report"] = data
        display(summary(data))
        progress_text.set(f"Finished — {len(data['files'])} JARs checked")
        save.configure(state=tk.NORMAL)
        copy.configure(state=tk.NORMAL)

    def export():
        path = filedialog.asksaveasfilename(defaultextension=".json", initialfile="jarcheck-report.json", filetypes=[("JSON report", "*.json")])
        if not path:
            return
        try:
            save_report(state["report"], path)
        except (ValueError, OSError) as exc:
            messagebox.showerror("Save failed", str(exc))

    def copy_results():
        root.clipboard_clear()
        root.clipboard_append(summary(state["report"]))
        progress_text.set("Results copied to clipboard")

    scan = tk.Button(controls, text="Choose mods folder", command=choose, padx=12)
    scan.pack(side=tk.LEFT, padx=6)
    save = tk.Button(controls, text="Save JSON report", command=export, state=tk.DISABLED, padx=12)
    save.pack(side=tk.LEFT, padx=6)
    copy = tk.Button(controls, text="Copy results", command=copy_results, state=tk.DISABLED, padx=12)
    copy.pack(side=tk.LEFT, padx=6)
    root.mainloop()


if __name__ == "__main__":
    main()
