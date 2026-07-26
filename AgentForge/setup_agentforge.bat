@echo off
:: =====================================================================
::  AgentForge - one-time environment setup
::
::  Replaces setup_infrastructure.ps1, which referenced two files that do
::  not exist (backend\requirements.txt and download_models.py) and could
::  never complete as written.
::
::  Torch is installed from the cu128 index. The cu121 build the old README
::  recommended has no sm_120 kernels and will not run on an RTX 50-series
::  (Blackwell) GPU.
:: =====================================================================
title AgentForge Setup
setlocal enabledelayedexpansion
cd /d "%~dp0"

echo ===================================================
echo             AgentForge Environment Setup
echo ===================================================
echo.

:: ---------------------------------------------------------------- checks
echo [1/6] Checking prerequisites...

py -3.12 --version >nul 2>&1
if errorlevel 1 (
    echo   [FAIL] Python 3.12 not found. Install it and re-run.
    echo          The project pins 3.12; 3.13 has no matching wheels for some deps.
    goto :fail
)
for /f "tokens=*" %%v in ('py -3.12 --version') do echo   [ OK ] %%v

nvidia-smi --query-gpu=name,memory.total,driver_version --format=csv,noheader >nul 2>&1
if errorlevel 1 (
    echo   [WARN] nvidia-smi not found. GPU acceleration will be unavailable.
) else (
    for /f "tokens=*" %%g in ('nvidia-smi --query-gpu^=name^,memory.total^,driver_version --format^=csv^,noheader') do echo   [ OK ] GPU: %%g
)

if not exist "models\Qwen3.5-4B-Q4_K_M.gguf" (
    echo   [FAIL] Missing models\Qwen3.5-4B-Q4_K_M.gguf
    goto :fail
)
echo   [ OK ] LLM weights present

if not exist "models\GLM-OCR\model.safetensors" (
    echo   [FAIL] Missing models\GLM-OCR\model.safetensors
    goto :fail
)
echo   [ OK ] Vision OCR weights present

if not exist "llama.cpp\build\bin\Release\llama-server.exe" (
    echo   [FAIL] Missing llama.cpp\build\bin\Release\llama-server.exe
    echo          Build llama.cpp with CUDA support before running setup.
    goto :fail
)
echo   [ OK ] llama-server binary present

:: ------------------------------------------------------------------ venv
echo.
echo [2/6] Creating virtual environment (venv\)...
py -3.12 -m venv --clear venv
if errorlevel 1 goto :fail
call venv\Scripts\activate.bat
python -m pip install --upgrade pip wheel setuptools --quiet
if errorlevel 1 goto :fail
echo   [ OK ] venv ready

:: ----------------------------------------------------------------- torch
echo.
echo [3/6] Installing PyTorch (CUDA 12.8 build, ~2.5 GB - this takes a while)...
python -m pip install torch torchvision --index-url https://download.pytorch.org/whl/cu128
if errorlevel 1 goto :fail
echo   [ OK ] torch installed

:: ------------------------------------------------------------------ deps
echo.
echo [4/6] Installing application dependencies...
python -m pip install -r requirements.txt
if errorlevel 1 goto :fail
echo   [ OK ] dependencies installed

:: -------------------------------------------------------------- chromium
echo.
echo [5/6] Installing Chromium for Crawl4AI...
python -m playwright install chromium
if errorlevel 1 (
    echo   [WARN] Chromium install failed. Scraping will fall back to BeautifulSoup.
) else (
    echo   [ OK ] Chromium installed
)

:: ---------------------------------------------------------- verification
echo.
echo [6/6] Verifying GPU stack...
python -c "import torch;assert torch.cuda.is_available(),'CUDA not available';cap=torch.cuda.get_device_capability(0);print('   device      :',torch.cuda.get_device_name(0));print('   capability  : sm_%d%d'%cap);print('   torch/cuda  :',torch.__version__,'/',torch.version.cuda);print('   total VRAM  : %.1f GiB'%(torch.cuda.get_device_properties(0).total_memory/1024**3));a=torch.randn(1024,1024,device='cuda',dtype=torch.bfloat16);_=(a@a).float().mean();print('   kernel test : PASS')"
if errorlevel 1 (
    echo   [FAIL] GPU verification failed - the installed torch has no kernels for this GPU.
    goto :fail
)

echo.
echo ===================================================
echo  Setup complete. Run start_agentforge.bat next.
echo ===================================================
pause
exit /b 0

:fail
echo.
echo ===================================================
echo  Setup FAILED. See the message above.
echo ===================================================
pause
exit /b 1
