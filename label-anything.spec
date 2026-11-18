# -*- mode: python ; coding: utf-8 -*-
"""Spec PyInstaller per Label Anything (onedir, windowed)."""

import os

block_cipher = None

APP_VERSION = os.environ.get("APP_VERSION", "dev")

# INCLUDI_AI=1 (con requirements-build-ai.txt installato) produce la variante
# "AI" del bundle: ultralytics/torch inclusi, inferenza in-app disponibile.
INCLUDI_AI = os.environ.get("INCLUDI_AI", "") == "1"

if INCLUDI_AI:
    from PyInstaller.utils.hooks import collect_all

    ai_datas, ai_binaries, ai_hiddenimports = collect_all("ultralytics")

    # alleggerimenti: dati torch di sviluppo (test/include e bin di test:
    # torch/bin/torch_shm_manager serve a runtime) e .py gia' nel PYZ
    def _da_scartare_ai(dest):
        if dest.startswith(("torch/test", "torch/include")):
            return True
        if dest.startswith("torch/bin"):
            return not dest.startswith("torch/bin/torch_shm_manager")
        return False

    ai_datas = [d for d in ai_datas if not _da_scartare_ai(d[0])]
    ai_binaries = [b for b in ai_binaries if not _da_scartare_ai(b[0])]
    ai_datas = [
        d for d in ai_datas
        if not (d[0].endswith(".py") and (d[0].startswith("torch/") or d[0].startswith("ultralytics/")))
    ]
else:
    ai_datas, ai_binaries, ai_hiddenimports = [], [], []

a = Analysis(
    ["run_labeling.py"],
    pathex=[],
    binaries=ai_binaries,
    datas=ai_datas,
    hiddenimports=ai_hiddenimports,
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
    ] + (["polars"] if INCLUDI_AI else []),
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
if INCLUDI_AI:
    # ultralytics scarica i pesi via HTTPS: servono le librerie TLS
    _esclusioni_plugin = tuple(
        x for x in _esclusioni_plugin
        if x not in ("libcrypto-3-x64", "libssl-3-x64", "plugins/tls", "plugins/networkinformation")
    )
a.binaries = [b for b in a.binaries if not any(x in b[0].lower() for x in _esclusioni_plugin)]
a.datas = [d for d in a.datas if not any(x in d[0].lower() for x in _esclusioni_plugin)]

if INCLUDI_AI:
    # anche l'hook torch contribuisce a.datas/a.binaries: stessi scarti
    a.binaries = [b for b in a.binaries if not _da_scartare_ai(b[0])]
    a.datas = [d for d in a.datas if not _da_scartare_ai(d[0])]
    a.datas = [
        d for d in a.datas
        if not (d[0].endswith(".py") and (d[0].startswith("torch/") or d[0].startswith("ultralytics/")))
    ]

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
