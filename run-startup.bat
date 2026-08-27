@echo off
cd /d "%~dp0"
"C:\Program Files\Python313\pythonw.exe" -m pip install -r requirements.txt -q
"C:\Program Files\Python313\pythonw.exe" src\app.py
