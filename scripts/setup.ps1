$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
$envPath = Join-Path $projectRoot '.env'
if (Test-Path -LiteralPath $envPath) {
    Write-Host '.env already exists; configuration preserved.'
    return
}
function New-Secret {
    $bytes = New-Object byte[] 32
    $generator = [System.Security.Cryptography.RandomNumberGenerator]::Create()
    try { $generator.GetBytes($bytes) } finally { $generator.Dispose() }
    return [Convert]::ToBase64String($bytes).Replace('+', '-').Replace('/', '_').TrimEnd('=')
}
$databaseSecret = New-Secret
$adminSecret = New-Secret
$configuration = @"
POSTGRES_USER=quiz
POSTGRES_DB=quiz
POSTGRES_PASSWORD=$databaseSecret
ADMIN_USERNAME=admin
ADMIN_EMAIL=admin@example.com
ADMIN_PASSWORD=$adminSecret
APP_ORIGINS=http://localhost:8080,http://localhost:5173,http://127.0.0.1:5173
COOKIE_SECURE=false
WEB_PORT=8080
"@
[IO.File]::WriteAllText($envPath, $configuration, [Text.UTF8Encoding]::new($false))
Write-Host 'Created .env with random passwords. Admin username: admin.'
Write-Host 'Read ADMIN_PASSWORD in .env to log in. Keep this file private.'
