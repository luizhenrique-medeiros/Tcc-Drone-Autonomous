[CmdletBinding()]
param()

$ErrorActionPreference = 'Stop'
$projectRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$backendPath = Join-Path $projectRoot 'backend'
$pythonCommand = Join-Path $backendPath '.venv\Scripts\python.exe'
if (-not (Test-Path $pythonCommand)) { $pythonCommand = 'python' }
Push-Location $backendPath
try {
    & $pythonCommand scripts/seed.py
    if ($LASTEXITCODE -ne 0) { throw "Seed falhou com exit code $LASTEXITCODE." }
}
finally { Pop-Location }
