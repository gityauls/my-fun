# exe 한 개로 묶는다. 빌드: .venv/Scripts/python.exe -m PyInstaller --noconfirm my-fun.spec
from PyInstaller.utils.hooks import collect_all

datas = [("funplayer/assets", "funplayer/assets")]
binaries, hidden = [], []
for package in ("av", "sounddevice", "_sounddevice_data"):
    d, b, h = collect_all(package)
    datas += d
    binaries += b
    hidden += h

a = Analysis(
    ["tools/run_my_fun.py"],
    pathex=["."],
    binaries=binaries,
    datas=datas,
    hiddenimports=hidden,
    excludes=["PySide6", "PySide2", "PyQt6", "tkinter", "pytest"],
)
pyz = PYZ(a.pure)
exe = EXE(
    pyz, a.scripts, a.binaries, a.datas, [],
    name="my-fun",
    icon="funplayer/assets/my-fun.ico",
    console=False,
    upx=False,
)
