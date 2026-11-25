[CmdletBinding()]
param([switch]$ValidateOnly)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
$root = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$router = Join-Path $env:LOCALAPPDATA 'DevCoreMavlinkRouter\Scripts\python.exe'
$routerScript = Join-Path $PSScriptRoot 'px4_router_daemon.py'
$gateway = Join-Path $root 'drone_gateway\.venv\Scripts\python.exe'
foreach ($path in @($router, $routerScript, $gateway)) {
    if (-not (Test-Path -LiteralPath $path -PathType Leaf)) { throw "Executavel ausente: $path" }
}
if ($ValidateOnly) {
    Write-Output 'Executaveis encontrados; nenhum processo iniciado.'
    return
}

$mutex = [Threading.Mutex]::new($false, 'Local\DevCorePx4ConnectionSupervisor')
$owned = $false
try {
    try { $owned = $mutex.WaitOne(0) } catch [Threading.AbandonedMutexException] { $owned = $true }
    if (-not $owned) { return }
    $logDir = Join-Path $env:LOCALAPPDATA 'DevCoreMavlinkRouter\logs'
    New-Item -ItemType Directory -Path $logDir -Force | Out-Null
    $routerChild = $null
    $gatewayChild = $null
    while ($true) {
        $processes = @(Get-CimInstance Win32_Process -Filter "Name = 'python.exe'")
        $routerPresent = @($processes | Where-Object {
            $_.ExecutablePath -eq $router -and (
                ($_.CommandLine -match '\s-m\s+MAVProxy\.mavproxy\s' -and
                 $_.CommandLine -match '--master=COM7(?:\s|$)') -or
                $_.CommandLine -match 'px4_router_daemon\.py'
            )
        }).Count -gt 0
        $gatewayPresent = @($processes | Where-Object {
            $_.ExecutablePath -eq $gateway -and $_.CommandLine -match '\s-m\s+app\.main(?:\s|$)'
        }).Count -gt 0
        if (-not $routerPresent -and ($null -eq $routerChild -or $routerChild.HasExited)) {
            $routerChild = Start-Process -FilePath $router -ArgumentList @('-u', "`"$routerScript`"") `
                -WorkingDirectory $logDir -WindowStyle Hidden -PassThru `
                -RedirectStandardOutput (Join-Path $logDir 'router.out.log') `
                -RedirectStandardError (Join-Path $logDir 'router.err.log')
        }
        if (-not $gatewayPresent -and ($null -eq $gatewayChild -or $gatewayChild.HasExited)) {
            # Process-level overrides take precedence over .env, including after Windows login.
            $env:GATEWAY_RUNTIME = 'host'
            $env:AUTOPILOT_SYSTEM = 'PX4'
            $env:MAVLINK_MODE = 'mavlink_router'
            $env:MAVLINK_CONNECTION = 'udpin:127.0.0.1:14600'
            # This supervisor owns the dedicated COM7 radio route, not QGC UDP forwarding.
            $env:MAVLINK_FORWARD_SOURCE = 'HARDWARE_REAL'
            $env:API_BASE_URL = 'http://127.0.0.1:8000'
            foreach ($name in @('REAL_HARDWARE_ACKNOWLEDGED', 'ALLOW_TELEMETRY_REQUESTS',
                'ALLOW_MISSION_UPLOAD', 'ALLOW_FLIGHT_COMMANDS', 'ALLOW_MISSION_START', 'ALLOW_VEHICLE_ARM')) {
                [Environment]::SetEnvironmentVariable($name, 'false', 'Process')
            }
            $gatewayChild = Start-Process -FilePath $gateway -ArgumentList @('-m', 'app.main') `
                -WorkingDirectory (Join-Path $root 'drone_gateway') -WindowStyle Hidden -PassThru `
                -RedirectStandardOutput (Join-Path $logDir 'gateway.out.log') `
                -RedirectStandardError (Join-Path $logDir 'gateway.err.log')
        }
        Start-Sleep -Seconds 15
    }
} finally {
    if ($owned) { $mutex.ReleaseMutex() }
    $mutex.Dispose()
}
