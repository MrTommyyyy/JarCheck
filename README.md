# JarCheck

A small, offline Minecraft mod-folder checker. It finds **byte-for-byte identical JARs**, even when their names differ, and validates ZIP/JAR integrity. It never deletes, edits, or executes mods. No API key, subscription, or external Python packages required.

Version: **0.2.0**. This project is at an early stage.

[Download the latest release](https://github.com/MrTommyyyy/JarCheck/releases/latest) · [Report a bug](https://github.com/MrTommyyyy/JarCheck/issues/new?template=bug_report.md) · [Suggest an improvement](https://github.com/MrTommyyyy/JarCheck/issues/new?template=feature_request.md)

![Tests](https://github.com/MrTommyyyy/JarCheck/actions/workflows/tests.yml/badge.svg)

**Download format:** a ZIP containing Python source, a desktop interface and a Windows launcher. Python 3.11+ is required; this is not a standalone EXE.

## Why I'm building this

I enjoy modded Minecraft and want tools that make managing modpacks less frustrating. JarCheck focuses on a small but useful job: spotting accidental copies and damaged JARs without changing anyone's files. I want it to stay simple enough for beginners and useful enough to grow through real feedback.

## What's included

- A desktop window and a command-line interface.
- SHA-256 matching to find identical files with different names.
- Archive integrity checks with limits on large archives.
- JSON reports you can save and review.
- Checks for files that change during a scan.
- Automated tests on Windows, macOS, and Linux.
- Optional subfolder scanning with relative paths; symbolic links are skipped.
- Safe JSON exports from the terminal or desktop window.

## Changes in 0.2.0

- Added opt-in recursive scanning for packs that keep JARs in subfolders.
- Added `--output report.json` for saving reports directly from the terminal.
- Fixed desktop exports so choosing a JAR as the output cannot overwrite a mod.
- Report writes now use an atomic replacement: an incomplete JSON write keeps the previous report intact.
- Symbolic-link JARs are reported as skipped; symbolic-link directories are not traversed.
- Added five regression tests and a synthetic demo you can try without a modpack.

## Start on Windows

1. Install Python **3.11 or newer** from https://www.python.org/downloads/ and include the Python launcher. If offered, enable “Add Python to PATH”.
2. Extract this entire ZIP into a folder.
3. Double-click `START-WINDOWS.bat`.
4. Click **Choose mods folder** and select your Minecraft instance's `mods` folder.

The standard Windows Python installer normally includes Tkinter for the desktop window. On systems without Tkinter, use the command line below. Linux desktop users may need their distribution's Tkinter package. This release's scanner was tested automatically; the desktop interface still needs manual testing on Windows.

## Command line

```sh
python jarcheck.py "C:\path\to\instance\mods"
python jarcheck.py "C:\path\to\instance\mods" --json
python jarcheck.py "C:\path\to\instance\mods" --recursive --output report.json
python gui.py
```

Use `python3` instead of `python` if your system requires it. Exit codes: `0` = scan completed without findings, `1` = duplicate or validation finding, `2` = invalid input or folder access failure.

Report output must end in `.json` and must not be a symbolic link. Saving to an existing report replaces that report. The desktop window has an **Include subfolders** checkbox; it is off by default.

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
