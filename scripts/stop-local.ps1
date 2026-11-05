$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
$pidFile = Join-Path $projectRoot '.local\dev-processes.json'
if (-not (Test-Path -LiteralPath $pidFile)) { Write-Host 'No local app processes recorded.'; return }
$state = Get-Content -Raw -LiteralPath $pidFile | ConvertFrom-Json
foreach ($kind in @('backend', 'frontend')) {
    $process = Get-Process -Id $state.$kind -ErrorAction SilentlyContinue
    $startedKey = "${kind}Started"
    if ($process -and $process.StartTime.ToUniversalTime().ToString('o') -eq $state.$startedKey) {
        if ($state.visibleTerminals) {
            & "$env:SystemRoot\System32\taskkill.exe" /PID $process.Id /T /F | Out-Null
        } else {
            Stop-Process -Id $process.Id
        }
    }
}
$expectedData = [IO.Path]::GetFullPath((Join-Path $projectRoot '.local\dev-postgres'))
if ($state.pgData -and [IO.Path]::GetFullPath($state.pgData) -eq $expectedData) {
    & (Join-Path $state.pgBin 'pg_ctl.exe') -D $state.pgData -m fast -w stop
}
Remove-Item -LiteralPath $pidFile
Write-Host 'Local app stopped. Database files preserved.'
