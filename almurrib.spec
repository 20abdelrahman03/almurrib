# PyInstaller build spec for Almurrib (GUI, windowed, single-file).
# Build with:  pyinstaller almurrib.spec

a = Analysis(
    ["src/almurrib/gui/app.py"],
    pathex=["src"],
    binaries=[],
    datas=[],
    hiddenimports=["tkinter", "tkinter.ttk", "tkinter.filedialog", "tkinter.messagebox"],
    hookspath=[],
    runtime_hooks=[],
    excludes=[],
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name="Almurrib",
    debug=False,
    strip=False,
    upx=True,
    console=False,   # windowed app — no console window
    disable_windowed_traceback=False,
)
