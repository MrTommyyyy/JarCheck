"""Read-only JAR folder audit. Python 3.11+, standard library only."""
from __future__ import annotations

import argparse
import hashlib
import json
import zipfile
from collections import defaultdict
from pathlib import Path

VERSION = "0.1.0"
MAX_UNPACKED_BYTES = 128 * 1024 * 1024
MAX_ENTRIES = 10_000


def audit(folder: str | Path) -> dict:
    """Inspect top-level JARs; never modify them or execute their contents."""
    folder = Path(folder)
    if not folder.is_dir():
        raise ValueError("Choose an existing folder.")
    records = []
    hashes = defaultdict(list)
    for path in sorted(folder.iterdir(), key=lambda p: p.name.casefold()):
        if not path.is_file() or path.suffix.lower() != ".jar":
            continue
        record = {"name": path.name, "status": "ok", "detail": ""}
        records.append(record)
        try:
            with path.open("rb") as stream:
                digest = hashlib.file_digest(stream, "sha256").hexdigest()
            record["sha256"] = digest
            hashes[digest].append(path.name)
            with zipfile.ZipFile(path) as archive:
                entries = archive.infolist()
                if len(entries) > MAX_ENTRIES or sum(e.file_size for e in entries) > MAX_UNPACKED_BYTES:
                    record.update(status="unchecked", detail="Archive exceeds validation limits; CRC check skipped.")
                    continue
                bad_member = archive.testzip()
                if bad_member is not None:
                    record.update(status="damaged", detail=f"CRC check failed: {bad_member}")
        except OSError as exc:
            record.update(status="unreadable", detail=str(exc))
        except Exception as exc:
            # Unsupported/encrypted ZIPs and malformed archives remain findings.
            record.update(status="invalid", detail=f"Could not validate as JAR/ZIP: {type(exc).__name__}: {exc}")
    return {
        "tool": "JarCheck", "version": VERSION,
        "files": records,
        "identical_groups": [names for names in hashes.values() if len(names) > 1],
        "limits": {"max_unpacked_bytes": MAX_UNPACKED_BYTES, "max_entries": MAX_ENTRIES},
    }


def summary(report: dict) -> str:
    lines = [f"JarCheck — {len(report['files'])} JAR file(s)"]
    for group in report["identical_groups"]:
        lines.append("Identical contents: " + " | ".join(group))
    for item in report["files"]:
        if item["status"] != "ok":
            lines.append(f"{item['status'].upper()}: {item['name']} — {item['detail']}")
    if not report["identical_groups"] and all(r["status"] == "ok" for r in report["files"]):
        lines.append("No identical JARs or archive integrity problems detected.")
    lines.append("This does not check mod compatibility, dependencies, or malware.")
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("folder", type=Path, help="Minecraft mods folder (top-level JARs only)")
    parser.add_argument("--json", action="store_true", help="Print a JSON report")
    parser.add_argument("--version", action="version", version=VERSION)
    args = parser.parse_args()
    try:
        report = audit(args.folder)
    except (ValueError, OSError) as exc:
        parser.error(str(exc))
    print(json.dumps(report, indent=2) if args.json else summary(report))
    return int(bool(report["identical_groups"]) or any(r["status"] != "ok" for r in report["files"]))


if __name__ == "__main__":
    raise SystemExit(main())
