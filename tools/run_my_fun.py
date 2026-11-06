"""exe의 시작점. 빌드: .venv/Scripts/python.exe -m PyInstaller --noconfirm my-fun.spec"""
import sys

from funplayer.__main__ import main

sys.exit(main())
