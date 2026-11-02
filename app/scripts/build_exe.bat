@echo off
REM Build a standalone Windows .exe for Flow-LoL.
REM Run this batch file from the project root in a normal Command Prompt or PowerShell.

setlocal EnableDelayedExpansion

REM Switch to the project root (the folder containing this script's parent).
cd /d "%~dp0\.."

REM ------------------------------------------------------------------
REM 1. Activate the project virtual environment.
REM    The venv is expected next to the script's parent folder (app\.venv).
REM ------------------------------------------------------------------
if not exist ".venv\Scripts\activate.bat" (
    echo ERROR: Virtual environment not found at .venv\Scripts\activate.bat
    echo Please create a venv or edit this script to point to the right Python.
    pause
    exit /b 1
)
call .venv\Scripts\activate.bat

REM ------------------------------------------------------------------
REM 2. Clean old build artifacts so we always ship fresh code.
REM ------------------------------------------------------------------
if exist "dist" rmdir /s /q "dist"
if exist "build" rmdir /s /q "build"
del /q "FlowLoL.spec" 2>nul

REM ------------------------------------------------------------------
REM 3. Install/update PyInstaller and project dependencies.
REM ------------------------------------------------------------------
python -m pip install --upgrade pyinstaller
python -m pip install -r requirements.txt

REM ------------------------------------------------------------------
REM 4. Run PyInstaller.
REM    - onefile: single .exe file (easier to share).
REM    - noconsole: no black terminal window appears behind the GUI.
REM    - collect-all: bundles hidden PyQt6 / OpenCV / BLE data files.
REM    - hidden-import: modules PyInstaller may not find automatically.
REM ------------------------------------------------------------------
pyinstaller ^
  --name FlowLoL ^
  --onefile ^
  --noconsole ^
  --icon NONE ^
  --add-data "flow_lol;flow_lol" ^
  --add-data "config.json;config.json" ^
  --collect-all PyQt6 ^
  --collect-all PyQt6-Qt6 ^
  --collect-all bleak ^
  --collect-all cv2 ^
  --collect-all sklearn ^
  --collect-all torch ^
  --collect-all sqlalchemy ^
  --collect-all polar_python ^
  --collect-all pycaw ^
  --hidden-import pycaw ^
  --hidden-import pycaw.pycaw ^
  --hidden-import pycaw.api ^
  --hidden-import pycaw.constants ^
  --hidden-import pycaw.mic ^
  --hidden-import comtypes ^
  --hidden-import comtypes.client ^
  --hidden-import comtypes.client.dynamic ^
  --hidden-import comtypes.stream ^
  --hidden-import comtypes.automation ^
  --hidden-import comtypes.typeinfo ^
  --hidden-import comtypes.GUID ^
  --hidden-import comtypes.persist ^
  --hidden-import comtypes.gen ^
  --hidden-import comtypes._meta ^
  --hidden-import comtypes.tools ^
  --hidden-import scipy.special ^
  --hidden-import sklearn.utils._typedefs ^
  --hidden-import sklearn.neighbors._partition_nodes ^
  --hidden-import sklearn.tree._utils ^
  --hidden-import flow_lol.persistence.database ^
  --hidden-import flow_lol.utils.logging ^
  --collect-all xgboost ^
  flow_lol_launcher.py

if %errorlevel% neq 0 (
    echo ERROR: PyInstaller build failed.
    pause
    exit /b 1
)

REM ------------------------------------------------------------------
REM 5. Copy extra runtime files into dist/ so the .exe finds them.
REM ------------------------------------------------------------------
copy /y "config.json" "dist\config.json" >nul 2>&1
xcopy /e /i /y "models" "dist\models" >nul 2>&1

REM Also copy the native XGBoost DLL next to the bundle root so PyInstaller's
REM --collect-all can find it at runtime inside the onefile temp directory.
set "XGB_DLL="
if exist ".venv\Lib\site-packages\xgboost\lib\xgboost.dll" (
    set "XGB_DLL=.venv\Lib\site-packages\xgboost\lib\xgboost.dll"
) else if exist ".venv\Lib\site-packages\xgboost\xgboost.dll" (
    set "XGB_DLL=.venv\Lib\site-packages\xgboost\xgboost.dll"
)
if not "!XGB_DLL!"=="" (
    echo Bundling XGBoost native library: !XGB_DLL!
    if not exist "dist\lib" mkdir "dist\lib"
    if not exist "dist\Library\lib" mkdir "dist\Library\lib"
    if not exist "dist\Library\bin" mkdir "dist\Library\bin"
    copy /y "!XGB_DLL!" "dist\xgboost.dll" >nul 2>&1
    copy /y "!XGB_DLL!" "dist\lib\xgboost.dll" >nul 2>&1
    copy /y "!XGB_DLL!" "dist\Library\lib\xgboost.dll" >nul 2>&1
    copy /y "!XGB_DLL!" "dist\Library\bin\xgboost.dll" >nul 2>&1
) else (
    echo WARNING: xgboost.dll not found in venv; XGBoost will be skipped at runtime.
)

REM ------------------------------------------------------------------
REM 6. Create a deployment folder that you can zip and send.
REM ------------------------------------------------------------------
if exist "FlowLoL-Deploy" rmdir /s /q "FlowLoL-Deploy"
if exist "FlowLoL-Deploy" (
    echo ERROR: Could not remove old FlowLoL-Deploy folder. Is FlowLoL.exe still running?
    pause
    exit /b 1
)
mkdir "FlowLoL-Deploy"
copy /y "dist\FlowLoL.exe" "FlowLoL-Deploy\FlowLoL.exe"
if not exist "FlowLoL-Deploy\FlowLoL.exe" (
    echo ERROR: Could not copy dist\FlowLoL.exe to FlowLoL-Deploy\. Is FlowLoL.exe still running?
    pause
    exit /b 1
)
copy /y "README-TESTER.txt" "FlowLoL-Deploy\README-TESTER.txt" >nul 2>&1
xcopy /e /i /y "models" "FlowLoL-Deploy\models" >nul 2>&1

echo.
echo Build complete.
echo   - Single .exe:   dist\FlowLoL.exe
echo   - Deploy folder: FlowLoL-Deploy\
echo.
pause
