$ErrorActionPreference = "Stop"

Set-Location (Resolve-Path (Join-Path $PSScriptRoot ".."))
$repoRoot = (Get-Location).Path
$frontendDir = Join-Path $repoRoot "frontend"

Write-Host "Starting backend (FastAPI) on http://127.0.0.1:8000 ..."
Start-Process powershell -WorkingDirectory $repoRoot -ArgumentList "uvicorn feature_achievement.api.main:app --reload"

Write-Host "Building graph-core (TypeScript) ..."
Push-Location $frontendDir
npm run build:core

Write-Host "Starting frontend server on http://127.0.0.1:5500 ..."
Start-Process powershell -WorkingDirectory $frontendDir -ArgumentList "python -m http.server 5500"
Pop-Location

Write-Host "Done. Open http://127.0.0.1:5500/index.html"
