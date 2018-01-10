# -*- mode: python -*-

block_cipher = None


a = Analysis(['server.py'],
             pathex=['/Users/laffra/PycharmProjects/Ikke'],
             binaries=[],
             datas=[
                ('installation/*', 'installation'),
                ('localsearch/*', 'localsearch'),
                ('html/*', 'html'),
                ('html/dothis/*', 'html/dothis'),
                ('html/icons/*', 'html/icons'),
                ('html/3rd/*', 'html/3rd'),
                ('html/3rd/jquery-ui-1.12.1/*', 'html/3rd/jquery-ui-1.12.1'),
                ('html/3rd/jquery-ui-1.12.1/external/*', 'html/3rd/jquery-ui-1.12.1/external'),
                ('html/3rd/jquery-ui-1.12.1/external/jquery/*', 'html/3rd/jquery-ui-1.12.1/external'),
                ('html/3rd/jquery-ui-1.12.1/images/*', 'html/3rd/jquery-ui-1.12.1/images'),
             ],
             hiddenimports=[
                'importers',
                'importers.browser',
                'importers.contact',
                'importers.download'
                'importers.facebook'
                'importers.file',
                'importers.gmail',
             ],
             hookspath=[],
             runtime_hooks=[],
             excludes=[],
             win_no_prefer_redirects=False,
             win_private_assemblies=False,
             cipher=block_cipher)
pyz = PYZ(a.pure, a.zipped_data,
             cipher=block_cipher)
exe = EXE(pyz,
          a.scripts,
          a.binaries,
          a.zipfiles,
          a.datas,
          name='ikke',
          debug=False,
          strip=False,
          upx=True,
          runtime_tmpdir=None,
          console=False )
app = BUNDLE(exe,
             name='ikke.app',
             icon=None,
             bundle_identifier=None)
