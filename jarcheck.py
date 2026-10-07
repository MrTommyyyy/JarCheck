"""Offline JAR audit with opt-in recoverable duplicate cleanup. Python 3.11+."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import tempfile
import zipfile
from collections import defaultdict
from pathlib import Path, PurePosixPath

VERSION = "0.4.0"
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


def duplicate_plan(report: dict, keepers=()) -> list[dict]:
    """Choose one keeper per healthy byte-identical group; never infer mod versions."""
    records = {item["name"]: item for item in report["files"]}
    selected = set(keepers)
    plans = []
    for group in report["identical_groups"]:
        if len(group) < 2 or any(name not in records or records[name]["status"] != "ok" for name in group):
            continue
        digest = records[group[0]].get("sha256")
        if not digest or any(records[name].get("sha256") != digest for name in group):
            raise ValueError("Duplicate report contains inconsistent hashes.")
        choices = selected.intersection(group)
        if len(choices) > 1:
            raise ValueError("Choose exactly one keeper per duplicate group.")
        keeper = next(iter(choices)) if choices else group[0]
        plans.append({"keep": keeper, "remove": [name for name in group if name != keeper], "sha256": digest})
    return plans


def _local_jar(root: Path, name: str) -> Path:
    parts = PurePosixPath(name).parts
    if (not parts or name.startswith("/") or "\\" in name or ":" in name
            or any(part in ("", ".", "..") for part in name.split("/"))
            or Path(name).suffix.lower() != ".jar"):
        raise ValueError("Recovery paths must be relative JAR paths.")
    candidate = root
    for part in parts:
        candidate = candidate / part
        if candidate.is_symlink():
            raise ValueError(f"Symbolic links are not moved: {name}")
    return candidate


def _verified_jar(root: Path, name: str, digest: str) -> Path:
    path = _local_jar(root, name)
    before = path.stat()
    if not path.is_file():
        raise ValueError(f"Not a regular file: {name}")
    with path.open("rb") as stream:
        current = hashlib.file_digest(stream, "sha256").hexdigest()
    after = path.stat()
    fields = ("st_dev", "st_ino", "st_size", "st_mtime_ns")
    if current != digest or any(getattr(before, key) != getattr(after, key) for key in fields):
        raise ValueError(f"File changed since the scan: {name}. Scan again before cleanup.")
    return path


def quarantine_duplicates(folder: str | Path, report: dict, keepers=()) -> dict:
    """Move verified extra copies to a sibling recovery folder, preserving one keeper."""
    root = Path(folder).resolve(strict=True)
    plans = duplicate_plan(report, keepers)
    if not plans:
        return {"recovery_folder": None, "moved": []}
    for plan in plans:
        for name in [plan["keep"], *plan["remove"]]:
            _verified_jar(root, name, plan["sha256"])
    base = root.parent / "JarCheck-Recovery"
    if base == root or root == root.parent or base.is_symlink():
        raise ValueError("Choose a mods folder with a separate parent for recovery files.")
    base.mkdir(exist_ok=True)
    recovery = Path(tempfile.mkdtemp(prefix=root.name + "-", dir=base))
    moves = [{"name": name, "sha256": plan["sha256"]} for plan in plans for name in plan["remove"]]
    manifest = {"format": "jarcheck-recovery/v1", "source_folder": str(root), "moves": moves}
    save_report(manifest, recovery / "recovery.json")
    moved = []
    try:
        for plan in plans:
            for name in plan["remove"]:
                _verified_jar(root, plan["keep"], plan["sha256"])
                source = _verified_jar(root, name, plan["sha256"])
                target = _local_jar(recovery, name)
                target.parent.mkdir(parents=True, exist_ok=True)
                if target.exists():
                    raise ValueError(f"Recovery destination already exists: {name}")
                source.rename(target)
                moved.append(name)
    except (OSError, ValueError) as error:
        raise ValueError(f"Cleanup stopped. {len(moved)} file(s) moved to {recovery}; the recovery record is preserved. {error}") from error
    return {"recovery_folder": str(recovery), "moved": moved}


def restore_duplicates(recovery_folder: str | Path) -> list[str]:
    """Restore recovery JARs without replacing any files already in the source folder."""
    recovery = Path(recovery_folder).resolve(strict=True)
    manifest = json.loads((recovery / "recovery.json").read_text(encoding="utf-8"))
    if not isinstance(manifest, dict) or manifest.get("format") != "jarcheck-recovery/v1" or not isinstance(manifest.get("moves"), list):
        raise ValueError("Unsupported recovery record.")
    root = Path(manifest["source_folder"]).resolve(strict=True)
    pending = []
    seen = set()
    for item in manifest["moves"]:
        if not isinstance(item, dict) or not isinstance(item.get("name"), str) or not isinstance(item.get("sha256"), str):
            raise ValueError("Malformed recovery entry.")
        name = item["name"]
        if name in seen:
            raise ValueError("Duplicate path in recovery record.")
        seen.add(name)
        source = _local_jar(recovery, name)
        target = _local_jar(root, name)
        if not source.exists():
            continue  # Already restored or manually moved out of recovery.
        _verified_jar(recovery, name, item["sha256"])
        if target.exists():
            raise ValueError(f"Restore cannot overwrite an existing file: {name}")
        pending.append((source, target, item["sha256"], name))
    restored = []
    for source, target, digest, name in pending:
        _verified_jar(recovery, name, digest)
        _local_jar(root, name)
        if target.exists():
            raise ValueError(f"Restore cannot overwrite an existing file: {name}")
        target.parent.mkdir(parents=True, exist_ok=True)
        # Link then unlink keeps the destination creation exclusive; never overwrite.
        os.link(source, target)
        source.unlink()
        restored.append(name)
    return restored


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
    parser.add_argument("folder", type=Path, nargs="?", help="Minecraft mods folder")
    parser.add_argument("--json", action="store_true", help="Print a JSON report")
    parser.add_argument("--recursive", action="store_true", help="Include nested folders without following symbolic links")
    parser.add_argument("--output", type=Path, help="Save a JSON report to a .json file (replaces an existing report)")
    parser.add_argument("--version", action="version", version=VERSION)
    parser.add_argument("--quarantine-duplicates", action="store_true", help="Move healthy identical extras to a sibling recovery folder; keeps the first sorted name")
    parser.add_argument("--restore", type=Path, help="Restore JARs from a JarCheck recovery folder")
    args = parser.parse_args()
    try:
        if args.restore:
            if args.folder or args.quarantine_duplicates or args.output:
                parser.error("Use --restore on its own.")
            restored = restore_duplicates(args.restore)
            print(f"Restored {len(restored)} JAR file(s).")
            return 0
        if args.folder is None:
            parser.error("Choose a mods folder or use --restore.")
        report = audit(args.folder, recursive=args.recursive)
        if args.quarantine_duplicates:
            result = quarantine_duplicates(args.folder, report)
            report = audit(args.folder, recursive=args.recursive)
            report["cleanup"] = result
            if not args.json:
                print(f"Moved {len(result['moved'])} duplicate(s). Recovery folder: {result['recovery_folder'] or 'none'}")
        if args.output:
            save_report(report, args.output)
    except (ValueError, OSError, KeyError, TypeError) as exc:
        parser.error(str(exc))
    print(json.dumps(report, indent=2) if args.json else summary(report))
    return int(bool(report["identical_groups"]) or any(r["status"] != "ok" for r in report["files"]))


if __name__ == "__main__":
    raise SystemExit(main())
