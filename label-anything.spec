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

_esclusioni_plugin = ("qtwebengine", "qt3d", "qtquick", "qtvirtualkeyboard")
a.binaries = [b for b in a.binaries if not any(x in b[0].lower() for x in _esclusioni_plugin)]
a.datas = [d for d in a.datas if not any(x in d[0].lower() for x in _esclusioni_plugin)]

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
