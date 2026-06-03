@echo off
echo ===================================================
4: echo   LogDay WFH Python Agent Build Script
5: echo ===================================================
6: 
7: cd /d "%~dp0"
8: 
9: if not exist venv\Scripts\activate.bat (
10:     echo [ERROR] Virtual environment 'venv' not found in this folder!
11:     echo Please run setup_wfh.bat first.
12:     pause
13:     exit /b
14: )
15: 
16: echo Activating virtual environment...
17: call venv\Scripts\activate
18: 
19: echo Installing/upgrading PyInstaller...
20: python -m pip install --upgrade pip
21: pip install pyinstaller
22: 
23: echo Building agent standalone directory using PyInstaller...
24: pyinstaller --noconfirm --onedir --windowed --name "wfh-agent" --clean main.py
25: 
26: echo.
27: echo ===================================================
28: echo   Agent build completed!
29: echo   Output is located in: agent\dist\wfh-agent\
30: echo ===================================================
31: pause
