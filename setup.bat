@echo off
rem One-time setup: virtual environment, requirements, face models, then a first-run check.
setlocal
cd /d "%~dp0"
title ClassVision setup

echo ClassVision setup
echo.

set "PY="
for %%V in (3.13 3.12 3.11 3.10) do call :try py -%%V
if not defined PY call :try python
if not defined PY goto :nopython
echo Using: %PY%

if exist ".venv\Scripts\python.exe" goto :haveenv
echo Creating a virtual environment in .venv ...
%PY% -m venv .venv
if errorlevel 1 goto :fail
:haveenv

echo.
echo Installing requirements (the first time takes a few minutes) ...
".venv\Scripts\python.exe" -m pip install --upgrade pip
".venv\Scripts\python.exe" -m pip install -r requirements.txt
if errorlevel 1 goto :fail
echo done> ".venv\.setup_done"

echo.
echo Fetching the face models ...
".venv\Scripts\python.exe" scripts\download_models.py
if errorlevel 1 echo The download failed. The app will offer to retry, or copy the two .onnx files into the models folder (see README).

echo.
echo Running the first-run check ...
".venv\Scripts\python.exe" scripts\doctor.py

echo.
echo Setup finished. Start the app with run.bat
if /i not "%~1"=="quiet" pause
exit /b 0

:try
if defined PY goto :eof
%* -c "import sys; sys.exit(0 if sys.version_info[:2] >= (3, 10) and sys.version_info[:2] <= (3, 13) else 1)" >nul 2>nul
if not errorlevel 1 set "PY=%*"
goto :eof

:nopython
echo.
echo Python 3.10 to 3.13 was not found.
echo Install Python 3.12 from https://www.python.org/downloads/ , tick "Add python.exe to PATH", then run setup.bat again.
pause
exit /b 1

:fail
echo.
echo Setup stopped because a step failed (often the internet connection). Read the messages above, fix the problem and run setup.bat again.
pause
exit /b 1
