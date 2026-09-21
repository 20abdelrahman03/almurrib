# PyInstaller build spec for Almurrib (GUI, windowed, single-file).
# Build with:  pyinstaller almurrib.spec

from PyInstaller.utils.hooks import collect_data_files

# UnityPy 1.25 reads EVERY object through typetrees, and its fallback
# typetree package (resources/lzma.tpk) is a DATA file PyInstaller does
# not collect on its own. Without it, obj.read() fails on all objects
# (verified live: thousands of "none are readable"). No hook exists
# upstream, so collect it explicitly here.
unity_datas = collect_data_files("UnityPy", includes=["resources/*.tpk"])

a = Analysis(
    ["src/almurrib/gui/app.py"],
    pathex=["src"],
    binaries=[],
    datas=unity_datas,
    hiddenimports=["tkinter", "tkinter.ttk", "tkinter.filedialog", "tkinter.messagebox"],
    hookspath=[],
    runtime_hooks=[],
    # Unity is a first-class milestone: UnityPy (MIT, pinned) ships INSIDE
    # the EXE so one-click Unity works with zero installs. Only the true
    # heavyweight offline-NMT stack stays out (torch/ctranslate2, ~500MB):
    # Argos still needs a desktop Python env with almurrib[offline].
    excludes=["torch", "stanza", "ctranslate2", "sentencepiece",
              "argostranslate", "sacremoses"],
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
