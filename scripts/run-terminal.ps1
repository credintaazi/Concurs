param([Parameter(Mandatory)][ValidateSet('backend', 'frontend')][string]$Component)
$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
if ($Component -eq 'backend') {
    $Host.UI.RawUI.WindowTitle = 'Quiz Arena - Backend (FastAPI)'
    Set-Location -LiteralPath (Join-Path $projectRoot 'backend')
    Write-Host 'Backend: http://127.0.0.1:8000/api/docs' -ForegroundColor Cyan
    & (Join-Path $projectRoot '.venv\Scripts\python.exe') -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload --reload-dir app
} else {
    $Host.UI.RawUI.WindowTitle = 'Quiz Arena - Frontend (React + Vite)'
    Set-Location -LiteralPath (Join-Path $projectRoot 'frontend')
    Write-Host 'Application: http://localhost:5173' -ForegroundColor Cyan
    npm.cmd run dev -- --port 5173 --strictPort
}
