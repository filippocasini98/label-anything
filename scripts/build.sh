#!/usr/bin/env bash
# Build locale riproducibile di Label Anything (onedir, windowed).
# Uso: APP_VERSION=v1.2.0 ./scripts/build.sh

set -euo pipefail
cd "$(dirname "$0")/.."

if [ ! -d venv ] && [ "${SKIP_VENV:-0}" != "1" ]; then
    python3 -m venv venv
    ./venv/bin/pip install --upgrade pip
fi

PIP="./venv/bin/pip"
[ -d venv ] || PIP="pip"
$PIP install -r requirements-build.txt pyinstaller

APP_VERSION="${APP_VERSION:-dev}" ./venv/bin/pyinstaller --noconfirm label-anything.spec 2>/dev/null \
    || APP_VERSION="${APP_VERSION:-dev}" pyinstaller --noconfirm label-anything.spec

echo
echo "Build completata: dist/LabelAnything/"

if [ "$(uname -s)" = "Darwin" ]; then
    # assembla Label Anything.app (layout onedir + symlink Frameworks)
    APP_DIR="dist/Label Anything.app"
    rm -rf "$APP_DIR"
    mkdir -p "$APP_DIR/Contents/MacOS" "$APP_DIR/Contents/Resources"
    cp -R dist/LabelAnything/. "$APP_DIR/Contents/MacOS/"
    ln -s MacOS/_internal "$APP_DIR/Contents/Frameworks"
    sed "s/@VERSIONE@/${APP_VERSION:-dev}/g" scripts/Info-macos.plist > "$APP_DIR/Contents/Info.plist"
    echo "Bundle: $APP_DIR"
fi
