# Preflight Script (Windows PowerShell)
# Run this before pushing to ensure CI will pass
# Usage: ./scripts/preflight.ps1

$ErrorActionPreference = "Stop"

Write-Host "==========================================" -ForegroundColor Cyan
Write-Host "🚀 PREFLIGHT CHECK - verified-digital-twin-brain" -ForegroundColor Cyan
Write-Host "==========================================" -ForegroundColor Cyan

# Get repo root
$RepoRoot = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
Set-Location $RepoRoot

Write-Host ""
Write-Host "📁 Repo root: $RepoRoot"

# ==========================================
# FRONTEND PREFLIGHT
# ==========================================
Write-Host ""
Write-Host "==========================================" -ForegroundColor Yellow
Write-Host "📦 FRONTEND PREFLIGHT" -ForegroundColor Yellow
Write-Host "==========================================" -ForegroundColor Yellow

Set-Location "$RepoRoot/frontend"

Write-Host "→ Installing dependencies (npm ci)..."
npm ci --silent
if ($LASTEXITCODE -ne 0) { throw "npm ci failed" }

Write-Host "→ Running lint..."
npm run lint
if ($LASTEXITCODE -ne 0) { throw "npm run lint failed" }

Write-Host "→ Running typecheck..."
npm run typecheck
if ($LASTEXITCODE -ne 0) { throw "npm run typecheck failed" }

Write-Host "→ Running build..."
npm run build
if ($LASTEXITCODE -ne 0) { throw "npm run build failed" }

Write-Host "✅ Frontend preflight passed!" -ForegroundColor Green

# ==========================================
# BACKEND PREFLIGHT
# ==========================================
Write-Host ""
Write-Host "==========================================" -ForegroundColor Yellow
Write-Host "🐍 BACKEND PREFLIGHT" -ForegroundColor Yellow
Write-Host "==========================================" -ForegroundColor Yellow

Set-Location "$RepoRoot/backend"

Write-Host "→ Installing dependencies..."
pip install -r requirements.txt -q
if ($LASTEXITCODE -ne 0) { throw "pip install failed" }

Write-Host "→ Running flake8 (syntax errors only)..."
python -m flake8 . --count --select=E9,F63,F7,F82 --show-source --statistics --exclude=.venv,venv,env,__pycache__,.git
if ($LASTEXITCODE -ne 0) { throw "flake8 failed" }

Write-Host "→ Running tests..."
python -m pytest -v --tb=short
if ($LASTEXITCODE -ne 0) { throw "pytest failed" }

Write-Host "✅ Backend preflight passed!" -ForegroundColor Green

# ==========================================
# FINAL CHECK
# ==========================================
Write-Host ""
Write-Host "==========================================" -ForegroundColor Green
Write-Host "✅ ALL PREFLIGHT CHECKS PASSED!" -ForegroundColor Green
Write-Host "   Safe to push to GitHub." -ForegroundColor Green
Write-Host "==========================================" -ForegroundColor Green

Set-Location $RepoRoot
