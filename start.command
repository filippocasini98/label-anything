#!/bin/bash
# Avvia Label Anything su macOS: doppio clic o ./start.command
cd "$(dirname "$0")"
if [ ! -x "./venv/bin/python" ]; then
    echo "Ambiente non trovato: esegui prima setup.command (una volta sola)."
    read -r -p "Premi Invio per chiudere..."
    exit 1
fi
exec "./venv/bin/python" run_labeling.py "$@"
