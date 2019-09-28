import sys
from cx_Freeze import setup, Executable

setup(
    name = "ffnorma",
    version = "0.1",
    executables = [Executable("ffnorma.py", base = "Win32GUI", icon="yellow-icon.ico")])
