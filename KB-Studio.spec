# -*- mode: python ; coding: utf-8 -*-


a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=[],
    datas=[('src/lark_syntax/grammar.lark', 'src/lark_syntax'), ('src/resources/themes', 'src/resources/themes')],
    hiddenimports=['src.resources.themes', 'src.lark_syntax.parser', 'lark'],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

# Use the system fontconfig: the copy from the build distribution is older
# than the configuration files shipped by newer distributions.
binaries = [b for b in a.binaries if not b[0].startswith('libfontconfig')]

exe = EXE(
    pyz,
    a.scripts,
    binaries,
    a.datas,
    [],
    name='KB-Studio',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
