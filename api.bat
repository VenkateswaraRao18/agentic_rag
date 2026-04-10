@echo off
REM Close ALL other uvicorn windows first — two processes on :8000 will mix old/new /health.
cd /d "%~dp0"
set PYTHONPATH=%CD%
echo PYTHONPATH=%PYTHONPATH%
echo Starting http://127.0.0.1:8000 — /health must include code_revision
.\.venv\Scripts\python.exe -m uvicorn run_api:app --reload --host 127.0.0.1 --port 8000
