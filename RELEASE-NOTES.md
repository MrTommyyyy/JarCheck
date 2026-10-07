JarCheck 0.4.0 adds duplicate cleanup with a preview and recovery.

Choose a copy to keep from each healthy identical group. Extra copies move to a sibling JarCheck-Recovery folder; Restore recovery folder puts them back without overwriting existing files. Hashes are rechecked before moves, and a recovery record is preserved if cleanup stops partway through.

Windows users: extract JarCheck-0.4.0-Windows-x64.zip and open JarCheck.exe. JarCheck-CLI.exe is included. Python is bundled. Source users need Python 3.11+.

Scanning remains read-only; cleanup needs explicit confirmation. Close Minecraft and your launcher first. This does not determine mod compatibility or malware safety.

Validation: 24 core tests and four actual Tk interface tests, plus packaged CLI behaviour and desktop executable startup checks in Windows CI. File-dialog responses in interface tests use synthetic inputs. These checks do not cover every real modpack or Windows configuration.
