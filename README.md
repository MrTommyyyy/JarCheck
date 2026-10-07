# JarCheck

A small, offline Minecraft mod-folder checker. It finds **byte-for-byte identical JARs**, even when their names differ, and validates ZIP/JAR integrity. Scanning never changes or executes mods. Optional duplicate cleanup moves extra copies out of your mods folder into a recoverable backup; it does not permanently delete them. No API key, subscription, or external Python packages required.

Version: **0.4.0**. This project is at an early stage.

[Download the latest release](https://github.com/MrTommyyyy/JarCheck/releases/latest) · [Report a bug](https://github.com/MrTommyyyy/JarCheck/issues/new?template=bug_report.md) · [Suggest an improvement](https://github.com/MrTommyyyy/JarCheck/issues/new?template=feature_request.md)

![Tests](https://github.com/MrTommyyyy/JarCheck/actions/workflows/tests.yml/badge.svg)

**Windows download:** choose the `Windows-x64.zip` asset, extract it, and double-click `JarCheck.exe`. Python is bundled. `JarCheck-CLI.exe` is also included. The separate source ZIP is for Python users on Windows, macOS or Linux.

## Why I'm building this

I enjoy modded Minecraft and want tools that make managing modpacks less frustrating. JarCheck focuses on a small but useful job: spotting accidental copies and damaged JARs, then giving people a clear choice about moving duplicates. I want it to stay simple enough for beginners and useful enough to grow through real feedback.

## What's included

- A desktop window and a command-line interface.
- SHA-256 matching to find identical files with different names.
- Archive integrity checks with limits on large archives.
- JSON reports you can save and review.
- Checks for files that change during a scan.
- Automated tests on Windows, macOS, and Linux.
- Optional subfolder scanning with relative paths; symbolic links are skipped.
- Safe JSON exports from the terminal or desktop window.

## Changes in 0.4.0

- **Review duplicates** previews each group and lets you choose the JAR to keep.
- Extra healthy copies move to a sibling `JarCheck-Recovery` folder with a restore record.
- **Restore recovery folder** puts files back without overwriting existing files.
- Files are hashed again before moving; changed files stop cleanup.
- Cleanup and restoration run in the background so the window remains responsive.
- Nine cleanup regression tests and four tests that exercise the actual desktop widgets on Windows.

## Changes in 0.3.0

- Portable Windows executables for the desktop window and command line.
- Scan progress shows how many JARs have finished and the current filename.
- Copy the readable results directly to your clipboard.

## Changes in 0.2.0

- Added opt-in recursive scanning for packs that keep JARs in subfolders.
- Added `--output report.json` for saving reports directly from the terminal.
- Fixed desktop exports so choosing a JAR as the output cannot overwrite a mod.
- Report writes now use an atomic replacement: an incomplete JSON write keeps the previous report intact.
- Symbolic-link JARs are reported as skipped; symbolic-link directories are not traversed.
- Added five regression tests and a synthetic demo you can try without a modpack.

## Start from Python source on Windows

1. Install Python **3.11 or newer** from https://www.python.org/downloads/ and include the Python launcher. If offered, enable “Add Python to PATH”.
2. Extract this entire ZIP into a folder.
3. Double-click `START-WINDOWS.bat`.
4. Click **Choose mods folder** and select your Minecraft instance's `mods` folder.

The standard Windows Python installer normally includes Tkinter for the desktop window. On systems without Tkinter, use the command line below. Linux desktop users may need their distribution's Tkinter package. Windows CI exercises the desktop widgets with synthetic JARs and mocked file-dialog responses, and checks that the bundled desktop executable opens. Those are automated checks; try a backed-up copy of your own pack before using cleanup on it.

## Command line

```sh
python jarcheck.py "C:\path\to\instance\mods"
python jarcheck.py "C:\path\to\instance\mods" --json
python jarcheck.py "C:\path\to\instance\mods" --recursive --output report.json
python gui.py
```

Use `python3` instead of `python` if your system requires it. Exit codes: `0` = scan completed without findings, `1` = duplicate or validation finding, `2` = invalid input or folder access failure.

Report output must end in `.json` and must not be a symbolic link. Saving to an existing report replaces that report. The desktop window has an **Include subfolders** checkbox; it is off by default.

## Remove identical copies and restore them

1. Close Minecraft and your launcher, then scan your mods folder.
2. Click **Review duplicates…**. Choose one filename to keep per identical group.
3. Confirm **Move extra copies to recovery**. JarCheck rechecks hashes, moves the extras and rescans.
4. To undo, click **Restore recovery folder…** and select the specific backup folder containing `recovery.json`.

Only healthy byte-identical JARs are eligible. Different versions, damaged files and archives exceeding the validation limits are left alone. Recovery is created beside your mods folder, not inside it; the parent folder must be writable. No files are permanently deleted. Restoration refuses existing destination files instead of replacing them.

Terminal equivalents:

```sh
python jarcheck.py "C:\path\to\mods" --quarantine-duplicates --json
python jarcheck.py --restore "C:\path\to\JarCheck-Recovery\mods-example"
```

The CLI keeps the first filename in the scan's sorted order; use the desktop preview to choose a different copy. Keep the recovery folder until you are satisfied with the result. Its record contains your original absolute folder path, so review it before sharing. Cleanup is a best-effort idle-folder operation, not a transaction or a filesystem lock. If moving fails partway through, the error names the recovery folder and its record can restore files already moved. Filesystem permissions, a running launcher or unsupported hard links can stop a restore; backups remain available for a manual copy.

## Try it without your mods

```sh
python demo.py
```

The demo creates synthetic archives in a temporary folder, scans them, and removes that temporary folder when finished. It never opens your Minecraft installation. You'll see an identical pair and an invalid archive, so you can learn what the findings mean before checking a real pack.

## Understanding results

- **Identical contents:** files have the same SHA-256 hash. Review whether you accidentally installed copies. Back up before making changes yourself.
- **DAMAGED:** an archive member failed its CRC integrity check.
- **INVALID:** the archive could not be validated, including malformed, encrypted, or unsupported ZIPs. This is not proof of malware.
- **UNREADABLE:** an operating-system error prevented access.
- **UNCHECKED:** validation was skipped because an archive has more than 10,000 entries or over 128 MiB of declared uncompressed content. Its SHA-256 was still computed.
- **CHANGED:** the file's size, modification time, or identity changed during the scan, or it disappeared. Close the launcher and run the scan again. This is a best-effort check, not a locked filesystem snapshot.
- **SKIPPED:** a JAR path is a symbolic link. Scan the intended physical folder directly if you want to check it.

By default, only top-level `.jar` files are scanned. Enable `--recursive` or the desktop checkbox to include subfolders. A clean result **does not** prove mods are compatible, dependencies are present, versions match, or files are safe. Different versions of the same mod will normally have different contents and are not flagged as identical. Close Minecraft and avoid changing the folder during a scan.

## Minecraft versions and loaders

The scanner inspects files outside Minecraft, so it does not need a Fabric, Forge or NeoForge port and is independent of the Minecraft version. It checks Java Edition JAR archives, not Bedrock add-ons, and does not interpret loader metadata. There is no claim that every modpack or desktop configuration has been tested.

Reports contain filenames, hashes, status, and error details. Error messages can contain local paths; review reports before posting publicly. The program makes no network requests.

## Development

```sh
python -m unittest discover -s tests -v
```

See `CONTRIBUTING.md` for small, useful follow-up tasks. Licensed under MIT; see `LICENSE`.
