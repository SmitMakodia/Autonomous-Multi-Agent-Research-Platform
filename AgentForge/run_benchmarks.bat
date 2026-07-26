@echo off
:: =====================================================================
::  Regenerate every evidence file and figure in rework-proof/.
::
::  Order matters. The GPU-exclusive benchmarks need the backend stopped
::  so the two llama-server instances do not fight; the API-level ones
::  need it running. Each harness records "skipped" with a reason rather
::  than failing if its dependency is unavailable.
::
::  Full run takes roughly 25-40 minutes, most of it the OCR suite, which
::  performs a complete VRAM hot-swap for each of 30 images.
:: =====================================================================
title AgentForge Benchmarks
setlocal
cd /d "%~dp0"

if not exist "venv\Scripts\python.exe" (
    echo [FAIL] No virtual environment. Run setup_agentforge.bat first.
    pause
    exit /b 1
)
set "PY=venv\Scripts\python.exe"

echo ===================================================
echo        AgentForge Benchmark Suite
echo ===================================================

echo.
echo [1/4] CPU-only - retrieval quality and scaling
%PY% benchmarks\bench_retrieval.py

echo.
echo [2/4] GPU-exclusive - stopping the backend first
call stop_agentforge.bat >nul 2>&1
timeout /t 5 /nobreak >nul
%PY% benchmarks\bench_vram.py
%PY% benchmarks\bench_ocr.py

echo.
echo [3/4] Needs llama-server and the backend - starting them
start "AgentForge Backend" cmd /k "cd backend && call ..\venv\Scripts\activate.bat && python main.py"
echo       waiting for readiness...
set /a WAITED=0
:wait
curl -s -o nul --max-time 2 http://127.0.0.1:8081/ >nul 2>&1
if not errorlevel 1 goto ready
set /a WAITED+=2
if %WAITED% geq 120 (
    echo   [FAIL] backend did not start; skipping the API-level benchmarks
    goto figures
)
timeout /t 2 /nobreak >nul
goto wait
:ready
echo       ready.
%PY% benchmarks\bench_throughput.py
%PY% benchmarks\bench_routing.py
%PY% benchmarks\bench_scrape.py
%PY% benchmarks\bench_latency.py
%PY% benchmarks\bench_robustness.py
%PY% benchmarks\bench_concurrency.py
%PY% benchmarks\capture_screenshots.py

:figures
echo.
echo [4/4] Rendering figures
%PY% benchmarks\make_figures.py

echo.
echo ===================================================
echo  Done.
echo   Raw evidence : ..\rework-proof\evidence\
echo   Figures      : ..\rework-proof\assets\figures\
echo   Screenshots  : ..\rework-proof\assets\screenshots\
echo ===================================================
pause
