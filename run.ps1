# Запуск Music Parser API

$ProjectDir = $PSScriptRoot
Set-Location $ProjectDir

if (-not (Test-Path ".venv\Scripts\Activate.ps1")) {
    Write-Host "Venv не найден. Create: python -m venv .venv"
    python -m venv .venv
    & ".venv\Scripts\Activate.ps1"
    python -m pip install --upgrade pip
    pip install -r requirements.txt
}

& ".venv\Scripts\Activate.ps1"
uvicorn main:app --host 127.0.0.1 --port 8001 --reload
