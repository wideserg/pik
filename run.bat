@echo off
cd /d "%~dp0"
"C:\Program Files\Python313\python.exe" -m pip install -r requirements.txt -q
"C:\Program Files\Python313\python.exe" src\app.py
