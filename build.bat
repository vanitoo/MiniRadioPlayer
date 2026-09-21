@echo off
setlocal

echo Building MiniRadioPlayer.exe...

python -m pip install --upgrade pip
if errorlevel 1 exit /b 1

python -m pip install -r requirements.txt pyinstaller
if errorlevel 1 exit /b 1

python -m PyInstaller --clean --noconfirm --noconsole --onefile --name MiniRadioPlayer main.py
if errorlevel 1 exit /b 1

echo.
echo Build complete: dist\MiniRadioPlayer.exe
endlocal
