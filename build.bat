@echo off
setlocal

echo Building MiniRadioPlayer.exe...

python -m pip install --upgrade pip
if errorlevel 1 exit /b 1

python -m pip install -r requirements.txt pyinstaller pillow
if errorlevel 1 exit /b 1

python build_icon.py
if errorlevel 1 exit /b 1

python -m PyInstaller --clean --noconfirm --noconsole --onefile --name MiniRadioPlayer --icon assets\MiniRadioPlayer.ico --add-data "assets\MiniRadioPlayer.ico;assets" --add-data "assets\MiniRadioPlayer.svg;assets" main.py
if errorlevel 1 exit /b 1

echo.
echo Build complete: dist\MiniRadioPlayer.exe
endlocal
