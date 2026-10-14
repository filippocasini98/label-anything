@echo off
rem Avvia Label Anything su Windows: doppio clic o start.bat
cd /d "%~dp0"
if not exist "venv\Scripts\python.exe" (
    echo Ambiente non trovato: esegui prima setup.bat ^(una volta sola^).
    pause
    exit /b 1
)
venv\Scripts\python run_labeling.py %*
