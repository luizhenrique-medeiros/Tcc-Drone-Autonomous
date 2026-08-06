[CmdletBinding()]
param()

$ErrorActionPreference = 'Stop'
$projectRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$gatewayPath = Join-Path $projectRoot 'drone_gateway'
$pythonCommand = Join-Path $gatewayPath '.venv\Scripts\python.exe'
if (-not (Test-Path $pythonCommand)) { $pythonCommand = 'python' }
Push-Location $gatewayPath
try {
    & $pythonCommand -m app.main
    if ($LASTEXITCODE -ne 0) { throw "Gateway encerrou com exit code $LASTEXITCODE." }
}
finally { Pop-Location }
