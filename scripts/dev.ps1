# Local development helper for Windows.
# Uses the canonical env files: repo-root `.env` and `frontend/.env.local`.

param(
    [switch]$BackendOnly,
    [switch]$FrontendOnly
)

$ErrorActionPreference = "Stop"
$RepoRoot = Split-Path -Parent $PSScriptRoot

$rootEnv = Join-Path $RepoRoot ".env"
$rootEnvExample = Join-Path $RepoRoot ".env.example"
$frontendEnv = Join-Path $RepoRoot "frontend\.env.local"
$frontendEnvExample = Join-Path $RepoRoot "frontend\.env.example"

Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  Local Development Environment" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

if (-not (Test-Path $rootEnv)) {
    if (Test-Path $rootEnvExample) {
        Copy-Item $rootEnvExample $rootEnv
        Write-Host "[i] Created .env from .env.example. Fill in real backend values before continuing." -ForegroundColor Yellow
    } else {
        throw "Missing .env and .env.example at repo root."
    }
}

if (-not (Test-Path $frontendEnv)) {
    if (Test-Path $frontendEnvExample) {
        Copy-Item $frontendEnvExample $frontendEnv
        Write-Host "[i] Created frontend/.env.local from frontend/.env.example." -ForegroundColor Yellow
    } else {
        throw "Missing frontend/.env.local and frontend/.env.example."
    }
}

function Get-BackendActivateScript {
    $candidates = @(
        (Join-Path $RepoRoot "backend\.venv\Scripts\Activate.ps1"),
        (Join-Path $RepoRoot "backend\venv\Scripts\Activate.ps1")
    )
    foreach ($candidate in $candidates) {
        if (Test-Path $candidate) {
            return $candidate
        }
    }
    return $null
}

function Start-Backend {
    $backendPath = Join-Path $RepoRoot "backend"
    $activateScript = Get-BackendActivateScript

    $backendCmd = @"
Set-Location '$backendPath'
if (Test-Path '$activateScript') { & '$activateScript' }
python -m pip install -r requirements.txt
uvicorn main:app --reload --host 0.0.0.0 --port 8000
"@

    Start-Process powershell -ArgumentList "-NoExit", "-Command", $backendCmd | Out-Null
    Write-Host "[Backend] Started in a new terminal" -ForegroundColor Green
}

function Start-Frontend {
    $frontendPath = Join-Path $RepoRoot "frontend"

    $frontendCmd = @"
Set-Location '$frontendPath'
npm ci
npm run dev
"@

    Start-Process powershell -ArgumentList "-NoExit", "-Command", $frontendCmd | Out-Null
    Write-Host "[Frontend] Started in a new terminal" -ForegroundColor Blue
}

if (-not $FrontendOnly) {
    Start-Backend
}

if (-not $BackendOnly) {
    Start-Sleep -Seconds 2
    Start-Frontend
}

Write-Host ""
Write-Host "Backend:  http://localhost:8000" -ForegroundColor Green
Write-Host "Frontend: http://localhost:3000" -ForegroundColor Blue
Write-Host "Swagger:  http://localhost:8000/docs" -ForegroundColor Gray
