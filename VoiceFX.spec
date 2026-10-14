# -*- mode: python ; coding: utf-8 -*-
# PyInstaller 빌드 설정:  pyinstaller VoiceFX.spec --noconfirm   → dist/VoiceFX/VoiceFX.exe
import importlib.util
import os

from PyInstaller.utils.hooks import collect_dynamic_libs

# 소음 억제는 rnnoise.dll만 쓴다 (pyrnnoise 패키지는 FFmpeg 등 무거운 의존성을 끌고 오므로 제외)
_rnnoise_dir = next(iter(importlib.util.find_spec("pyrnnoise").submodule_search_locations))

a = Analysis(
    ["run_voicefx.py"],
    pathex=[],
    binaries=[(os.path.join(_rnnoise_dir, "rnnoise.dll"), ".")] + collect_dynamic_libs("pylibrb"),
    datas=[
        ("voicefx/ui", "voicefx/ui"),
        ("voicefx/assets", "voicefx/assets"),
        ("voicefx/locales", "voicefx/locales"),
    ],
    hiddenimports=["clr", "pycaw.pycaw", "comtypes.stream"],
    excludes=[
        "pyrnnoise", "audiolab", "av",
        "tkinter", "matplotlib", "PIL", "scipy", "pandas", "IPython", "pytest",
        "cryptography", "win32ui", "pythonwin", "win32com", "OpenSSL",
    ],
    noarchive=False,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="VoiceFX",
    console=False,  # 콘솔 창 없이 실행 (오류는 %APPDATA%\VoiceFX\voicefx.log)
    icon="voicefx/assets/icon.ico",
    upx=False,  # UPX 압축은 백신 오탐을 늘려서 끈다
)
coll = COLLECT(exe, a.binaries, a.datas, name="VoiceFX", upx=False)
