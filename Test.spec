# -*- mode: python -*-

block_cipher = None


a = Analysis(['Test.py'],
             pathex=[   'C:\\Users\\brt\\PycharmProjects\\TEST', 
                                'C:\\Users\\brt\\AppData\\Roaming\\Python\\Python35\\site-packages\\PyQt5\\Qt\\bin\\',
                                'C:\\Users\\brt\\AppData\\Roaming\\Python\\Python35\\site-packages\\numpy'],
             binaries=[''],
             datas=[('candy.cfg', '.')],
             hiddenimports=[],
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
          exclude_binaries=True,
          name='Test',
          debug=False,
          strip=False,
          upx=True,
          console=True )
          
coll = COLLECT(exe,
               a.binaries,
               a.zipfiles,
               a.datas,
               strip=False,
               upx=True,
               name='Test')
