@echo off
cd /d "%~dp0"
py -3 gui.py
if errorlevel 1 (
  echo Install Python 3.11 or newer with the Python launcher, then try again.
  echo You can also run: python gui.py
  pause
)
