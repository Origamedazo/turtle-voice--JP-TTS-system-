# -*- mode: python ; coding: utf-8 -*-
import os
import pyopenjtalk

pyopenjtalk_dir = os.path.dirname(pyopenjtalk.__file__)
dic_dir = os.path.join(pyopenjtalk_dir, 'open_jtalk_dic_utf_8-1.11')

a = Analysis(
    ['gui_main.py'],
    pathex=[],
    binaries=[],
    datas=[
        (dic_dir, os.path.join('pyopenjtalk', 'open_jtalk_dic_utf_8-1.11')),
        ('voicebanks', 'voicebanks'),
        ('user_dicts', 'user_dicts'),
        ('image.ico', '.'),
        ('image.png', '.'),
        ('ita_corpus.json', '.'),
        ('labConverter.py', '.'),
        ('F0er.py', '.'),
        ('phoneme_indexCreater.py', '.'),
    ],
    hiddenimports=['PyQt6.QtCore', 'PyQt6.QtGui', 'PyQt6.QtWidgets', 'numpy', 'pyopenjtalk', 'soundfile', 'librosa', 'pandas', 'scipy'],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='turtle_voice_GUI',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=['image.ico'],
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='turtle_voice_GUI',
)
