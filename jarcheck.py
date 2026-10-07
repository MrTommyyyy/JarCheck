"""Read-only JAR folder audit. Python 3.11+, standard library only."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import tempfile
import zipfile
from collections import defaultdict
from pathlib import Path

VERSION = "0.3.0"
MAX_UNPACKED_BYTES = 128 * 1024 * 1024
MAX_ENTRIES = 10_000


def audit(folder: str | Path, *, recursive: bool = False, progress=None) -> dict:
    """Inspect JARs without changing them. Never follow symbolic links."""
    folder = Path(folder)
    if not folder.is_dir():
        raise ValueError("Choose an existing folder.")
    records = []
    hashes = defaultdict(list)
    def candidates():
        if not recursive:
            yield from folder.iterdir()
            return
        def walk_error(exc):
            raise exc
        for parent, directories, names in os.walk(folder, followlinks=False, onerror=walk_error):
            directories[:] = [name for name in directories if not (Path(parent) / name).is_symlink()]
            for name in names:
                yield Path(parent) / name

    paths = [p for p in candidates() if p.suffix.lower() == ".jar" and (p.is_symlink() or p.is_file())]
    paths.sort(key=lambda p: (p.relative_to(folder).as_posix().casefold(), p.relative_to(folder).as_posix()))
    for index, path in enumerate(paths):
        if progress is not None:
            progress(index, len(paths), path.relative_to(folder).as_posix())
        if path.suffix.lower() != ".jar":
            continue
        name = path.relative_to(folder).as_posix()
        if path.is_symlink():
            records.append({"name": name, "status": "skipped", "detail": "Symbolic links are not scanned."})
            continue
        if not path.is_file():
            continue
        record = {"name": name, "status": "ok", "detail": ""}
        records.append(record)
        before = None
        digest = None
        try:
            before = path.stat()
            with path.open("rb") as stream:
                digest = hashlib.file_digest(stream, "sha256").hexdigest()
            record["sha256"] = digest
            with zipfile.ZipFile(path) as archive:
                entries = archive.infolist()
                if len(entries) > MAX_ENTRIES or sum(e.file_size for e in entries) > MAX_UNPACKED_BYTES:
                    record.update(status="unchecked", detail="Archive exceeds validation limits; CRC check skipped.")
                else:
                    bad_member = archive.testzip()
                    if bad_member is not None:
                        record.update(status="damaged", detail=f"CRC check failed: {bad_member}")
        except OSError as exc:
            record.update(status="unreadable", detail=str(exc))
        except Exception as exc:
            # Unsupported/encrypted ZIPs and malformed archives remain findings.
            record.update(status="invalid", detail=f"Could not validate as JAR/ZIP: {type(exc).__name__}: {exc}")
        if before is not None:
            try:
                after = path.stat()
                changed = (before.st_dev, before.st_ino, before.st_size, before.st_mtime_ns) != (after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns)
            except OSError:
                changed = True
            if changed:
                record.update(status="changed", detail="File changed or disappeared during the scan. Run the scan again when the folder is idle.")
                record.pop("sha256", None)
            elif digest is not None:
                hashes[digest].append(name)
    if progress is not None:
        progress(len(paths), len(paths), "")
    return {
        "tool": "JarCheck", "version": VERSION,
        "files": records, "recursive": recursive,
        "identical_groups": [names for names in hashes.values() if len(names) > 1],
        "limits": {"max_unpacked_bytes": MAX_UNPACKED_BYTES, "max_entries": MAX_ENTRIES},
    }


def save_report(report: dict, output: str | Path) -> None:
    """Atomically save JSON, refusing other extensions and symbolic links."""
    output = Path(output)
    if output.suffix.lower() != ".json":
        raise ValueError("Save reports as .json files; mod files cannot be used as report output.")
    if output.is_symlink():
        raise ValueError("Report output must not be a symbolic link.")
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=output.parent, prefix=".jarcheck-", suffix=".tmp", delete=False) as stream:
            temporary = Path(stream.name)
            json.dump(report, stream, indent=2, ensure_ascii=False)
            stream.write("\n")
        os.replace(temporary, output)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def summary(report: dict) -> str:
    lines = [f"JarCheck — {len(report['files'])} JAR file(s)"]
    for group in report["identical_groups"]:
        lines.append("Identical contents: " + " | ".join(group))
    for item in report["files"]:
        if item["status"] != "ok":
            lines.append(f"{item['status'].upper()}: {item['name']} — {item['detail']}")
    if not report["files"]:
        lines.append("No JAR files found. Check that you selected the instance's mods folder.")
    elif not report["identical_groups"] and all(r["status"] == "ok" for r in report["files"]):
        lines.append("No identical JARs or archive integrity problems detected.")
    lines.append("This does not check mod compatibility, dependencies, or malware.")
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("folder", type=Path, help="Minecraft mods folder (top-level JARs only)")
    parser.add_argument("--json", action="store_true", help="Print a JSON report")
    parser.add_argument("--recursive", action="store_true", help="Include nested folders without following symbolic links")
    parser.add_argument("--output", type=Path, help="Save a JSON report to a .json file (replaces an existing report)")
    parser.add_argument("--version", action="version", version=VERSION)
    args = parser.parse_args()
    try:
        report = audit(args.folder, recursive=args.recursive)
        if args.output:
            save_report(report, args.output)
    except (ValueError, OSError) as exc:
        parser.error(str(exc))
    print(json.dumps(report, indent=2) if args.json else summary(report))
    return int(bool(report["identical_groups"]) or any(r["status"] != "ok" for r in report["files"]))


if __name__ == "__main__":
    raise SystemExit(main())
