# Check if venv exists, if not create it
if (!(Test-Path "venv")) {
    Write-Host "Creating virtual environment..."
    python -m venv venv
}

# Activate venv
Write-Host "Activating virtual environment..."
.\venv\Scripts\Activate.ps1

# Install dependencies
Write-Host "Installing dependencies..."
pip install -r agentforge/requirements.txt

Write-Host "Setup complete. To activate the environment in the future, run: .\venv\Scripts\Activate.ps1"
