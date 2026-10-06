# Contributing

Try the tool on a copied mod folder first. Submit reproducible bugs, documentation improvements, or small changes with useful tests. Do not attach private logs, access tokens, or copyrighted mod JARs to issues; synthetic ZIP fixtures are enough for most bugs.

Useful next tasks:

- Manually test the desktop interface on Windows, macOS, and Linux.
- Add an optional recursive scan with clear handling of symlinks.
- Explore detecting multiple versions of the same mod using documented loader metadata; distinguish these from identical files.
- Add sample report screenshots using invented filenames.

Run `python -m unittest discover -s tests -v` before submitting a change. Keep scanning read-only and offline, and avoid claiming a clean scan guarantees compatibility or security.
