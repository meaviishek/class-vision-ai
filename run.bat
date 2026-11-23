@echo off
rem Starts ClassVision. Runs the one-time setup first if it has not been done yet.
setlocal
cd /d "%~dp0"
title ClassVision
if not exist ".venv\.setup_done" call setup.bat quiet
if not exist ".venv\.setup_done" exit /b 1
".venv\Scripts\python.exe" main.py
if errorlevel 1 (
  echo.
  echo ClassVision stopped with an error. Read the messages above, or run  .venv\Scripts\python.exe scripts\doctor.py
  pause
)
