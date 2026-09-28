from PyInstaller.utils.hooks import collect_all


# Pacotes que podem precisar de arquivos adicionais
datas = []
binaries = []
hiddenimports = []


# PyWebView
tmp = collect_all("webview")
datas += tmp[0]
binaries += tmp[1]
hiddenimports += tmp[2]


a = Analysis(
    ["app.py"],
    pathex=[],
    binaries=binaries,
    datas=datas + [
        ("templates", "templates"),
        ("static", "static"),
    ],
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
)


pyz = PYZ(a.pure)


exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name="Biblist",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    icon=r"assets\livros.ico",
)


coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    name="Biblist",
)
