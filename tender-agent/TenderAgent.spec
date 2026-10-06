# Сборка Windows-программы: pyinstaller TenderAgent.spec
# -*- mode: python ; coding: utf-8 -*-
import os

ONEFILE = os.environ.get("TA_ONEFILE", "1") == "1"

a = Analysis(
    ["main.py"],
    pathex=["."],
    datas=[
        ("tenderagent/sites/sites.json", "tenderagent/sites"),
        ("assets/icon.ico", "assets"),
        ("assets/icon.png", "assets"),
    ],
    hiddenimports=["win32com.client", "pythoncom", "truststore", "asn1crypto.cms"],
    excludes=["tkinter", "PySide6.QtWebEngineCore", "PySide6.QtWebEngineWidgets", "PySide6.Qt3DCore",
              "PySide6.QtQuick", "PySide6.QtQml", "PySide6.QtMultimedia", "PySide6.QtCharts",
              "PySide6.QtDataVisualization", "PySide6.QtPdf", "matplotlib", "numpy.tests"],
    noarchive=False,
)
pyz = PYZ(a.pure)

if ONEFILE:
    exe = EXE(pyz, a.scripts, a.binaries, a.datas, [], name="ТендерАгент", console=False,
              icon="assets/icon.ico", upx=False)
else:
    exe = EXE(pyz, a.scripts, [], exclude_binaries=True, name="ТендерАгент", console=False,
              icon="assets/icon.ico", upx=False)
    coll = COLLECT(exe, a.binaries, a.datas, name="ТендерАгент", upx=False)
