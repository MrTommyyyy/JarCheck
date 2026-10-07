# Changelog

## 0.4.0

- Preview duplicate groups and choose which healthy copy to keep.
- Recoverable cleanup with hash rechecks, a sibling backup folder and explicit restore.
- Refuse changed files, unsafe paths and overwriting files during restoration.
- Background cleanup and restore; narrow-window text wraps to fit.
- Nine cleanup tests and four actual Tk interface tests.

## 0.3.0

- Windows desktop and CLI executables; scan progress and clipboard results.
- Added regression tests for the new behaviour.

## 0.2.0

- Opt-in recursive scans with relative paths and no symbolic-link traversal.
- CLI JSON exports and shared atomic report saving for the desktop interface.
- Rejected non-JSON and symbolic-link report output to protect mod files.
- Five new regression tests and a self-contained synthetic demo.

## 0.1.1

- Changed files are flagged and excluded from identical-file groups.
- Clearer empty-folder guidance and a regression test for changes during hashing.

## 0.1.0

- Offline SHA-256 duplicate detection, capped archive integrity checks, desktop UI and CLI.
