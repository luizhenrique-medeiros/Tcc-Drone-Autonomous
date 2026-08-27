[CmdletBinding()]
param(
    [switch]$DiagnoseOnly,
    [ValidateRange(0, 60)][int]$ObserveSeconds = 5
)

$ErrorActionPreference = 'Stop'
$projectRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$gatewayPath = Join-Path $projectRoot 'drone_gateway'
$pythonCommand = Join-Path $gatewayPath '.venv\Scripts\python.exe'
if (-not (Test-Path $pythonCommand)) { $pythonCommand = 'python' }
$previousGatewayRuntime = $env:GATEWAY_RUNTIME
$env:GATEWAY_RUNTIME = 'host'
Push-Location $gatewayPath
try {
    if ($DiagnoseOnly) {
        Write-Host 'Diagnóstico MAVLink passivo: nenhum comando será enviado ao veículo.'
        & $pythonCommand -m app.tools.mavlink_diagnose --connect --observe-seconds $ObserveSeconds
        if ($LASTEXITCODE -ne 0) { throw "Diagnóstico encerrou com exit code $LASTEXITCODE." }
    }
    else {
        & $pythonCommand -m app.main
        if ($LASTEXITCODE -ne 0) { throw "Gateway encerrou com exit code $LASTEXITCODE." }
    }
}
finally {
    Pop-Location
    if ($null -eq $previousGatewayRuntime) {
        Remove-Item Env:GATEWAY_RUNTIME -ErrorAction SilentlyContinue
    }
    else {
        $env:GATEWAY_RUNTIME = $previousGatewayRuntime
    }
}
