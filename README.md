# JarCheck

A small, offline Minecraft mod-folder checker. It finds **byte-for-byte identical JARs**, even when their names differ, and validates ZIP/JAR integrity. It never deletes, edits, or executes mods. No API key, subscription, or external Python packages required.

Version: 0.1.0. This is a new, AI-assisted starter project. It has no claimed users, downloads, external contributors, or established adoption.

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
python gui.py
```

Use `python3` instead of `python` if your system requires it. Exit codes: `0` = scan completed without findings, `1` = duplicate or validation finding, `2` = invalid input or folder access failure.

## Understanding results

- **Identical contents:** files have the same SHA-256 hash. Review whether you accidentally installed copies. Back up before making changes yourself.
- **DAMAGED:** an archive member failed its CRC integrity check.
- **INVALID:** the archive could not be validated, including malformed, encrypted, or unsupported ZIPs. This is not proof of malware.
- **UNREADABLE:** an operating-system error prevented access.
- **UNCHECKED:** validation was skipped because an archive has more than 10,000 entries or over 128 MiB of declared uncompressed content. Its SHA-256 was still computed.

Only top-level `.jar` files are scanned. A clean result **does not** prove mods are compatible, dependencies are present, versions match, or files are safe. Different versions of the same mod will normally have different contents and are not flagged as identical. Close Minecraft and avoid changing the folder during a scan.

Reports contain filenames, hashes, status, and error details. Error messages can contain local paths; review reports before posting publicly. The program makes no network requests.

## Publish the source on GitHub

1. Sign in at https://github.com and create a new **public** repository named `jarcheck`.
2. Choose **uploading an existing file** (or **Add file → Upload files**).
3. Upload the extracted source files, including `README.md`, `LICENSE`, `jarcheck.py`, `gui.py`, and the `tests` folder; commit them. Upload the source, not only the ZIP.
4. If using Git, also include `.github/workflows/tests.yml` to enable the included automated checks. Browser uploads may omit hidden folders.
5. Read the code, try it with your own mod folder, and keep improving it as the maintainer.

Creating this repository does not establish eligibility for Anthropic's Claude for Open Source program. Its published criteria focus on existing adoption, contributions, or critical infrastructure: https://claude.com/contact-sales/claude-for-oss . Do not claim activity or adoption that has not happened.

## Development

```sh
python -m unittest discover -s tests -v
```

See `CONTRIBUTING.md` for small, useful follow-up tasks. Licensed under MIT; see `LICENSE`.
