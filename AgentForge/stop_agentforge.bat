@echo off
:: =====================================================================
::  AgentForge - stop
::
::  Asks uvicorn to shut down first so FastAPI's shutdown hook runs and
::  SQLite writes are flushed cleanly. The old version went straight to
::  taskkill /f, so the shutdown handler in main.py never executed.
:: =====================================================================
title AgentForge Shutdown
setlocal enabledelayedexpansion
cd /d "%~dp0"

echo ===================================================
echo             AgentForge Shutdown Sequence
echo ===================================================
echo.

echo [1/3] Requesting graceful shutdown...
:: Ctrl+Break to the backend console lets uvicorn run its shutdown handler,
:: which calls model_manager.stop_llm() and closes the DB cleanly.
set "FOUND="
for /f "tokens=5" %%a in ('netstat -aon ^| findstr /c:":8081 " ^| findstr "LISTENING"') do (
    for /f "usebackq delims=, tokens=1" %%n in (`tasklist /nh /fo csv /fi "PID eq %%a" 2^>nul`) do (
        if /i "%%~n"=="python.exe" (
            set "FOUND=1"
            echo   Signalling backend ^(PID %%a^)...
            taskkill /pid %%a >nul 2>&1
        )
    )
)
if defined FOUND (
    echo   Waiting up to 10s for clean exit...
    set /a WAITED=0
    :grace_loop
    curl -s -o nul --max-time 1 http://127.0.0.1:8081/ >nul 2>&1
    if errorlevel 1 goto :stopped
    set /a WAITED+=1
    if !WAITED! geq 10 goto :force
    timeout /t 1 /nobreak >nul
    goto :grace_loop
    :stopped
    echo   [ OK ] Backend exited cleanly
) else (
    echo   No backend listening on 8081
)
goto :after_backend

:force
echo   [WARN] Still responding - forcing termination
for /f "tokens=5" %%a in ('netstat -aon ^| findstr /c:":8081 " ^| findstr "LISTENING"') do taskkill /f /pid %%a >nul 2>&1

:after_backend
echo.
echo [2/3] Closing backend console window...
taskkill /fi "windowtitle eq AgentForge Backend*" >nul 2>&1

echo.
echo [3/3] Stopping LLM server and freeing VRAM...
taskkill /F /IM llama-server.exe /T >nul 2>&1
echo   [ OK ] llama-server stopped

nvidia-smi --query-gpu=memory.used,memory.total --format=csv,noheader >nul 2>&1
if not errorlevel 1 (
    for /f "tokens=*" %%m in ('nvidia-smi --query-gpu^=memory.used^,memory.total --format^=csv^,noheader') do echo   VRAM now: %%m
)

echo.
echo ===================================================
echo  AgentForge has been shut down.
echo ===================================================
pause
exit /b 0
