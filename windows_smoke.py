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

assert run("--version").strip() == "0.3.0"
with tempfile.TemporaryDirectory() as folder:
    folder = Path(folder)
    with zipfile.ZipFile(folder / "first.jar", "w") as archive:
        archive.writestr("payload.txt", "synthetic test")
    assert json.loads(run(folder, "--json"))["files"][0]["status"] == "ok"
    shutil.copyfile(folder / "first.jar", folder / "copy.jar")
    output = folder / "report.json"
    run(folder, "--output", output, code=1)
    assert json.loads(output.read_text())["identical_groups"] == [["copy.jar", "first.jar"]]
    run(folder / "missing", code=2)
print("Packaged executable smoke checks passed")
