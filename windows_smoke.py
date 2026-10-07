"""Exercise the packaged executable against disposable inputs."""
import json
from pathlib import Path
import shutil
import subprocess
import tempfile
import zipfile

EXE = Path("dist/JarCheck-CLI.exe").resolve()

def run(*args, code=0):
    result = subprocess.run([str(EXE), *map(str, args)], capture_output=True, text=True, timeout=60)
    if result.returncode != code:
        raise RuntimeError(f"Unexpected exit {result.returncode}: {result.stdout} {result.stderr}")
    return result.stdout

assert run("--version").strip() == "0.4.0"
with tempfile.TemporaryDirectory() as folder:
    folder = Path(folder)
    with zipfile.ZipFile(folder / "first.jar", "w") as archive:
        archive.writestr("payload.txt", "synthetic test")
    assert json.loads(run(folder, "--json"))["files"][0]["status"] == "ok"
    shutil.copyfile(folder / "first.jar", folder / "copy.jar")
    output = folder / "report.json"
    run(folder, "--output", output, code=1)
    assert json.loads(output.read_text())["identical_groups"] == [["copy.jar", "first.jar"]]
    cleaned = json.loads(run(folder, "--quarantine-duplicates", "--json"))
    assert cleaned["cleanup"]["moved"] == ["first.jar"]
    assert (folder / "copy.jar").exists() and not (folder / "first.jar").exists()
    run("--restore", cleaned["cleanup"]["recovery_folder"])
    assert (folder / "first.jar").read_bytes() == (folder / "copy.jar").read_bytes()
    shutil.rmtree(cleaned["cleanup"]["recovery_folder"])
    run(folder / "missing", code=2)
print("Packaged executable smoke checks passed")
