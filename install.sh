#!/bin/bash
# Scarica l'ultima versione di Label Anything da GitHub, la scompatta e prepara l'ambiente.
# Uso: curl -fsSL <url>/install.sh | bash
#   oppure, dopo aver scaricato questo file: bash install.sh
set -e

REPO="filippocasini98/label-anything"
DEST="label-anything"

need() { command -v "$1" >/dev/null 2>&1 || { echo "Errore: serve '$1' installato." >&2; exit 1; }; }
need curl
need unzip

echo "Scarico l'ultima versione di Label Anything..."
curl -fsSL -o /tmp/label-anything.zip "https://github.com/${REPO}/archive/refs/heads/main.zip"

echo "Scompatto in ./${DEST}/..."
rm -rf "${DEST}"
mkdir -p "${DEST}"
unzip -q /tmp/label-anything.zip -d "${DEST}"
rm -f /tmp/label-anything.zip
shopt -s dotglob nullglob
for f in "${DEST}"/label-anything-main/*; do mv "$f" "${DEST}/"; done
rmdir "${DEST}/label-anything-main" 2>/dev/null || true

echo "Preparo l'ambiente (crea il venv e installa le dipendenze)..."
bash "${DEST}/setup.command"

echo ""
echo "Fatto! Per avviare: doppio clic su ${DEST}/start.command"
echo "oppure: ./${DEST}/venv/bin/python ${DEST}/run_labeling.py"
