param([int]$DatabasePort = 55433, [switch]$PostgreSQL, [switch]$VisibleTerminals, [switch]$SkipInstall, [string]$TunnelUrl)
$ErrorActionPreference = 'Stop'
$tunnelOrigin = $null
if ($TunnelUrl) {
    $tunnelUri = $null
    if (-not [Uri]::TryCreate($TunnelUrl, [UriKind]::Absolute, [ref]$tunnelUri) -or
        $tunnelUri.Scheme -ne 'https' -or -not $tunnelUri.Host -or $tunnelUri.UserInfo -or
        $tunnelUri.AbsolutePath -ne '/' -or $tunnelUri.Query -or $tunnelUri.Fragment) {
        throw 'TunnelUrl must be an HTTPS origin, for example https://YOUR-TUNNEL-5173.euw.devtunnels.ms (without a page path).'
    }
    $tunnelOrigin = $tunnelUri.GetLeftPart([UriPartial]::Authority)
}
$projectRoot = Split-Path -Parent $PSScriptRoot
Set-Location -LiteralPath $projectRoot
$pidFile = Join-Path $projectRoot '.local\dev-processes.json'
if (Test-Path -LiteralPath $pidFile) { throw 'Local process state already exists. Run scripts/stop-local.ps1 before restarting.' }
& (Join-Path $PSScriptRoot 'setup.ps1')
Get-Content -LiteralPath (Join-Path $projectRoot '.env') | ForEach-Object {
    if ($_ -match '^([A-Z_]+)=(.*)$') { [Environment]::SetEnvironmentVariable($matches[1], $matches[2], 'Process') }
}
$env:APP_ORIGINS = (@(($env:APP_ORIGINS -split ',') + @('http://localhost:5173', 'http://127.0.0.1:5173')) | Select-Object -Unique) -join ','
if ($tunnelOrigin) {
    $env:APP_ORIGINS = (@(($env:APP_ORIGINS -split ',') + @($tunnelOrigin)) | Select-Object -Unique) -join ','
    # Permit only this tunnel's hostname; keep Vite's host protection enabled.
    $env:__VITE_ADDITIONAL_SERVER_ALLOWED_HOSTS = $tunnelUri.Host
} else {
    Remove-Item Env:__VITE_ADDITIONAL_SERVER_ALLOWED_HOSTS -ErrorAction SilentlyContinue
}
$env:COOKIE_SECURE = 'false' # Local Vite is HTTP; deployment retains .env's setting.
$pgBin = $null
$pgData = $null
if ($PostgreSQL) {
    $pgCandidates = @('C:\Program Files\PostgreSQL\18\bin', 'C:\Program Files\PostgreSQL\17\bin', 'C:\Program Files\PostgreSQL\16\bin')
    $pgBin = $pgCandidates | Where-Object { Test-Path -LiteralPath (Join-Path $_ 'pg_ctl.exe') } | Select-Object -First 1
    if (-not $pgBin) { throw 'Install PostgreSQL 16+ or use Docker Compose.' }
    $localDir = Join-Path $projectRoot '.local'
    $pgData = Join-Path $localDir 'dev-postgres'
    New-Item -ItemType Directory -Force -Path $localDir | Out-Null
    if (-not (Test-Path -LiteralPath (Join-Path $pgData 'PG_VERSION'))) {
        $passwordFile = Join-Path $localDir 'init-password.tmp'
        try {
            [IO.File]::WriteAllText($passwordFile, $env:POSTGRES_PASSWORD, [Text.UTF8Encoding]::new($false))
            & (Join-Path $pgBin 'initdb.exe') -D $pgData -U $env:POSTGRES_USER -A scram-sha-256 --pwfile=$passwordFile --encoding=UTF8 --locale=C
            if ($LASTEXITCODE -ne 0) { throw 'PostgreSQL initialization failed.' }
        } finally { if (Test-Path -LiteralPath $passwordFile) { Remove-Item -LiteralPath $passwordFile } }
    }
    & (Join-Path $pgBin 'pg_ctl.exe') -D $pgData status *> $null
    if ($LASTEXITCODE -ne 0) {
        & (Join-Path $pgBin 'pg_ctl.exe') -D $pgData -l (Join-Path $localDir 'dev-postgres.log') -o "-p $DatabasePort -h 127.0.0.1" -w start
        if ($LASTEXITCODE -ne 0) { throw 'Could not start local PostgreSQL.' }
    }
    $env:PGPASSWORD = $env:POSTGRES_PASSWORD
    $databaseExists = & (Join-Path $pgBin 'psql.exe') -h 127.0.0.1 -p $DatabasePort -U $env:POSTGRES_USER -d postgres -tAc "SELECT 1 FROM pg_database WHERE datname = 'quiz'"
    if ($databaseExists -ne '1') {
        & (Join-Path $pgBin 'createdb.exe') -h 127.0.0.1 -p $DatabasePort -U $env:POSTGRES_USER quiz
        if ($LASTEXITCODE -ne 0) { throw 'Could not create database.' }
    }
    Remove-Item Env:PGPASSWORD
    $env:DB_HOST = '127.0.0.1'
    $env:DB_PORT = "$DatabasePort"
    $env:DB_USER = $env:POSTGRES_USER
    $env:DB_NAME = 'quiz'
    $env:DB_PASSWORD = $env:POSTGRES_PASSWORD
    Remove-Item Env:DATABASE_URL -ErrorAction SilentlyContinue
} else {
    if (-not $env:DATABASE_URL) { $env:DATABASE_URL = 'sqlite:///' + ((Join-Path $projectRoot '.local/quiz.sqlite3') -replace '\\', '/') }
    Write-Host 'Using SQLite; the database and tables are created automatically when missing.'
}
$localDir = Join-Path $projectRoot '.local'
New-Item -ItemType Directory -Force -Path $localDir | Out-Null
$python = Join-Path $projectRoot '.venv\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $python)) { python -m venv .venv }
if (-not $SkipInstall) {
    & $python -m pip install -e './backend[test]'
    if ($LASTEXITCODE -ne 0) { throw 'Python dependency installation failed.' }
}
Push-Location -LiteralPath (Join-Path $projectRoot 'backend')
try {
    & $python -m app.initialize
    if ($LASTEXITCODE -ne 0) { throw 'Database initialization failed.' }
} finally { Pop-Location }
if (-not $SkipInstall) {
    Push-Location -LiteralPath (Join-Path $projectRoot 'frontend')
    try {
        npm.cmd ci
        if ($LASTEXITCODE -ne 0) { throw 'Frontend dependency installation failed.' }
    } finally { Pop-Location }
}
if ($VisibleTerminals) {
    $terminalScript = Join-Path $PSScriptRoot 'run-terminal.ps1'
    $backendProcess = Start-Process -FilePath 'powershell.exe' -ArgumentList @('-NoProfile', '-NoExit', '-File', "`"$terminalScript`"", '-Component', 'backend') -WorkingDirectory $projectRoot -WindowStyle Normal -PassThru
    $frontendProcess = Start-Process -FilePath 'powershell.exe' -ArgumentList @('-NoProfile', '-NoExit', '-File', "`"$terminalScript`"", '-Component', 'frontend') -WorkingDirectory $projectRoot -WindowStyle Normal -PassThru
} else {
    $backendProcess = Start-Process -FilePath $python -ArgumentList @('-m', 'uvicorn', 'app.main:app', '--host', '127.0.0.1', '--port', '8000') -WorkingDirectory (Join-Path $projectRoot 'backend') -WindowStyle Hidden -PassThru -RedirectStandardOutput (Join-Path $localDir 'backend.log') -RedirectStandardError (Join-Path $localDir 'backend-error.log')
    $vitePath = Join-Path $projectRoot 'frontend\node_modules\vite\bin\vite.js'
    $frontendProcess = Start-Process -FilePath (Get-Command node.exe).Source -ArgumentList @("`"$vitePath`"", '--host', '127.0.0.1', '--port', '5173', '--strictPort') -WorkingDirectory (Join-Path $projectRoot 'frontend') -WindowStyle Hidden -PassThru -RedirectStandardOutput (Join-Path $localDir 'frontend.log') -RedirectStandardError (Join-Path $localDir 'frontend-error.log')
}
@{ backend = $backendProcess.Id; backendStarted = $backendProcess.StartTime.ToUniversalTime().ToString('o'); frontend = $frontendProcess.Id; frontendStarted = $frontendProcess.StartTime.ToUniversalTime().ToString('o'); visibleTerminals = [bool]$VisibleTerminals; pgBin = $pgBin; pgData = $pgData } | ConvertTo-Json | Set-Content -LiteralPath $pidFile
$ready = $false
for ($attempt = 0; $attempt -lt 30; $attempt++) {
    try {
        $health = Invoke-WebRequest -UseBasicParsing 'http://127.0.0.1:8000/api/v1/health' -TimeoutSec 2
        $web = Invoke-WebRequest -UseBasicParsing 'http://127.0.0.1:5173' -TimeoutSec 2
        if ($health.StatusCode -eq 200 -and $web.StatusCode -eq 200) { $ready = $true; break }
    } catch { Start-Sleep -Milliseconds 300 }
}
if (-not $ready) { throw 'App did not become ready. Read .local/*-error.log, then run scripts/stop-local.ps1.' }
Write-Host 'Application: http://localhost:5173'
if ($tunnelOrigin) { Write-Host "Tunnel: $tunnelOrigin (forward port 5173 in VS Code)" }
Write-Host 'Admin: http://localhost:5173/admin/login (password is in .env)'
Write-Host 'Stop with: .\scripts\stop-local.ps1'
