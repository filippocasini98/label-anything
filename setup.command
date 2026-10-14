#!/bin/bash
# Prepara l'ambiente di Label Anything: crea il venv e installa le dipendenze.
# Da eseguire una sola volta dopo aver ricevuto la cartella.
cd "$(dirname "$0")"

PYTHON=python3
command -v python3 >/dev/null 2>&1 || PYTHON=python

echo "Creo l'ambiente virtuale (venv)..."
"$PYTHON" -m venv venv || { echo "Errore: impossibile creare il venv (serve Python 3.9+)."; exit 1; }

echo "Installo le dipendenze (PySide6, OpenCV, numpy)..."
./venv/bin/python -m pip install --upgrade pip
./venv/bin/python -m pip install -r requirements.txt || { echo "Errore durante l'installazione delle dipendenze."; exit 1; }

echo ""
echo "Ambiente pronto. Avvia il programma con doppio clic su start.command"
read -r -p "Premi Invio per chiudere..."
