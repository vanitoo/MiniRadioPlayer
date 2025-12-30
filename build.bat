@echo off
echo Building MiniRadioPlayer.exe...
pip install pyinstaller
python -m pyinstaller --noconsole --name MiniRadioPlayer --onefile main.py
echo Build complete. Check dist/ folder.