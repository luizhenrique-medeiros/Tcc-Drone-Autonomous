[CmdletBinding()]
param(
    [switch]$SkipMigration,
    [string]$HostAddress = '127.0.0.1',
    [int]$Port = 8000
)

$ErrorActionPreference = 'Stop'
$projectRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$backendPath = Join-Path $projectRoot 'backend'
$pythonCommand = Join-Path $backendPath '.venv\Scripts\python.exe'
if (-not (Test-Path $pythonCommand)) { $pythonCommand = 'python' }

Push-Location $backendPath
try {
    if (-not $SkipMigration) {
        & $pythonCommand -m alembic upgrade head
        if ($LASTEXITCODE -ne 0) { throw "Migração falhou com exit code $LASTEXITCODE." }
    }
    & $pythonCommand scripts/seed.py
    if ($LASTEXITCODE -ne 0) { throw "Seed falhou com exit code $LASTEXITCODE." }
    Write-Host "Backend: http://localhost:$Port"
    & $pythonCommand -m uvicorn app.main:app --reload --host $HostAddress --port $Port
    if ($LASTEXITCODE -ne 0) { throw "Backend encerrou com exit code $LASTEXITCODE." }
}
finally { Pop-Location }
