# -*- mode: python ; coding: utf-8 -*-
"""Spec PyInstaller per Label Anything (onedir, windowed)."""

import os

block_cipher = None

APP_VERSION = os.environ.get("APP_VERSION", "dev")

a = Analysis(
    ["run_labeling.py"],
    pathex=[],
    binaries=[],
    datas=[],
    hiddenimports=[],
    hookspath=[],
    runtime_hooks=[],
    excludes=[
        "tkinter",
        "PySide6.QtWebEngineCore",
        "PySide6.QtWebEngineWidgets",
        "PySide6.QtQml",
        "PySide6.QtQuick",
        "PySide6.QtQuickWidgets",
        "PySide6.Qt3DCore",
        "PySide6.Qt3DRender",
        "PySide6.QtCharts",
        "PySide6.QtMultimedia",
        "PySide6.QtMultimediaWidgets",
        "PySide6.QtSql",
        "PySide6.QtTest",
        "PySide6.QtXml",
        "PySide6.QtDesigner",
        "PySide6.QtBluetooth",
        "PySide6.QtNfc",
        "PySide6.QtPositioning",
        "PySide6.QtSensors",
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

_esclusioni_plugin = (
    "qtwebengine", "qt3d", "qtquick", "qtvirtualkeyboard",
    "qtquick", "qtqml", "qtnetwork", "qtpdf",
    "qt6quick", "qt6qml", "qt6network", "qt6pdf",
    "opengl32sw", "videoio_ffmpeg", "qpdf", "plugins/networkinformation", "plugins/tls",
    "libcrypto-3-x64", "libssl-3-x64",
)
a.binaries = [b for b in a.binaries if not any(x in b[0].lower() for x in _esclusioni_plugin)]
a.datas = [d for d in a.datas if not any(x in d[0].lower() for x in _esclusioni_plugin)]

# rimuove le copie di libreria duplicate a livello radice: se lo stesso file
# esiste in una sottocartella (.libs/ rilocazioni dei wheel), i binari lo
# raggiungono via rpath $ORIGIN e la copia in radice e' sprecata
_nomi_in_sottocartelle = {b[0].rsplit("/", 1)[-1].lower() for b in a.binaries if "/" in b[0]}
a.binaries = [b for b in a.binaries if "/" in b[0] or b[0].lower() not in _nomi_in_sottocartelle]

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="LabelAnything",
    debug=False,
    strip=False,
    upx=False,
    console=False,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=False,
    name="LabelAnything",
)
