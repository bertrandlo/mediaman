#-*- coding: utf-8 -*-
from distutils.core import setup
import py2exe

setup(
    windows=['mediaman.py', {"script": "mediaman.py", "icon_resources": [(1, "icon.ico")]}],
    options={
        'py2exe': { 'bundle_files': 3,  # 3 - not bundle to single execute file
                    "packages": [],
                    "excludes": ["tcl", "Tkinter", "PySide"],
                    "includes": ["send2trash", "sip", "PyQt5.QtCore", "PyQt5.QtGui", "PyQt5.QtWidgets"],
                    "dll_excludes": ["mswsock.dll", "powrprof.dll", "tcl85.dll", "tk85.dll"]}
    },

    zipfile=None,
)