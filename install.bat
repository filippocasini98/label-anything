@echo off
rem Scarica l'ultima versione di Label Anything da GitHub, la scompatta e prepara l'ambiente.
rem Uso: scarica questo file ed eseguilo con doppio clic (serve curl, incluso in Windows 10+).

setlocal
set "REPO=filippocasini98/label-anything"
set "DEST=label-anything"

echo Scarico l'ultima versione di Label Anything...
curl -fsSL -o "%TEMP%\label-anything.zip" "https://github.com/%REPO%/archive/refs/heads/main.zip"
if errorlevel 1 (
    echo Errore durante lo scaricamento.
    pause
    exit /b 1
)

echo Scompatto in .\%DEST%\...
if exist "%DEST%" rmdir /s /q "%DEST%"
mkdir "%DEST%"
tar -xf "%TEMP%\label-anything.zip" -C "%DEST%"
del "%TEMP%\label-anything.zip"
move "%DEST%\label-anything-main\*" "%DEST%\" >nul

echo Preparo l'ambiente (crea il venv e installa le dipendenze)...
call "%DEST%\setup.bat"

echo.
echo Fatto! Per avviare: doppio clic su %DEST%\start.bat
pause
