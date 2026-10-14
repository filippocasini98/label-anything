@echo off
rem Prepara l'ambiente di Label Anything: crea il venv e installa le dipendenze.
rem Da eseguire una sola volta dopo aver ricevuto la cartella.
cd /d "%~dp0"

echo Creo l'ambiente virtuale (venv)...
python -m venv venv
if errorlevel 1 (
    echo Errore: impossibile creare il venv. Serve Python 3.9+ installato da python.org
    pause
    exit /b 1
)

echo Installo le dipendenze (PySide6, OpenCV, numpy)...
venv\Scripts\python -m pip install --upgrade pip
venv\Scripts\python -m pip install -r requirements.txt
if errorlevel 1 (
    echo Errore durante l'installazione delle dipendenze.
    pause
    exit /b 1
)

echo.
echo Ambiente pronto. Avvia il programma con doppio clic su start.bat
pause
