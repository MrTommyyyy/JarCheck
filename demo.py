"""Try JarCheck with synthetic archives in a disposable temporary folder."""
import shutil
import tempfile
import zipfile
from pathlib import Path

from jarcheck import audit, summary


def main():
    with tempfile.TemporaryDirectory(prefix="jarcheck-demo-") as temporary:
        folder = Path(temporary)
        with zipfile.ZipFile(folder / "example-mod.jar", "w") as archive:
            archive.writestr("example.txt", "A synthetic fixture, not a real Minecraft mod.")
        shutil.copyfile(folder / "example-mod.jar", folder / "example-mod-copy.jar")
        (folder / "broken-download.jar").write_text("A synthetic invalid archive.", encoding="utf-8")
        print("Synthetic demo: your Minecraft files are not used.\n")
        print(summary(audit(folder)))


if __name__ == "__main__":
    main()
