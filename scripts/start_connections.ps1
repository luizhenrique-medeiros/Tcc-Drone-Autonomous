[CmdletBinding()]
param(
    [switch]$ValidateOnly,
    [switch]$Build,
    [ValidateRange(2, 60)][int]$PollSeconds = 5,
    [string]$FlutterSdkRoot
)

# Reconnection is automatic; authority to mutate the vehicle never is.
Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
$projectRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$pythonPath = Join-Path $projectRoot 'drone_gateway\.venv\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $pythonPath)) {
    throw 'Crie o ambiente virtual do gateway conforme drone_gateway/README.md.'
}
$hash = [Security.Cryptography.SHA256]::Create()
try {
    $key = [BitConverter]::ToString($hash.ComputeHash([Text.Encoding]::UTF8.GetBytes($projectRoot.ToLowerInvariant()))).Replace('-', '').Substring(0, 16)
} finally { $hash.Dispose() }
$mutex = [Threading.Mutex]::new($false, "Local\DevcoreConnections-$key")
$ownsMutex = $false
$gatewayChild = $null
$mobileChild = $null
$logRoot = Join-Path ([IO.Path]::GetTempPath()) "devcore-connections-$key"

function Start-ObservedChild([string]$Name, [string]$Script, [string]$ExtraArguments) {
    $stamp = [DateTime]::UtcNow.ToString('yyyyMMdd-HHmmss-fff')
    $arguments = "-NoProfile -NonInteractive -ExecutionPolicy Bypass -File `"$Script`" $ExtraArguments"
    Start-Process -FilePath (Join-Path $PSHOME 'powershell.exe') -ArgumentList $arguments `
        -WorkingDirectory $projectRoot -WindowStyle Hidden -PassThru `
        -RedirectStandardOutput (Join-Path $logRoot "$Name-$stamp.out.log") `
        -RedirectStandardError (Join-Path $logRoot "$Name-$stamp.err.log")
}

function Test-ProjectGateway {
    # The venv launcher is retained while its child uses the base Python executable.
    $processes = @(Get-CimInstance Win32_Process -Filter "Name = 'python.exe'")
    return @($processes | Where-Object {
        $_.ExecutablePath -eq $pythonPath -and $_.CommandLine -match '\s-m\s+app\.main(?:\s|$)'
    }).Count -gt 0
}

try {
    try { $ownsMutex = $mutex.WaitOne(0) }
    catch [Threading.AbandonedMutexException] { $ownsMutex = $true }
    if (-not $ownsMutex) {
        Write-Host 'O supervisor deste projeto ja esta ativo. Nenhum processo duplicado foi iniciado.'
        return
    }
    $parameters = @{ ServicesOnly = $true; SkipDockerBuild = -not $Build; ValidateOnly = $ValidateOnly }
    if ($FlutterSdkRoot) { $parameters.FlutterSdkRoot = $FlutterSdkRoot }
    & (Join-Path $PSScriptRoot 'start_development.ps1') @parameters
    if ($ValidateOnly) {
        Write-Host 'Supervisor validado. Na execucao normal, novos gateways sempre usam os quatro gates false.'
        return
    }
    New-Item -ItemType Directory -Path $logRoot -Force | Out-Null
    Write-Host "Supervisao ativa. Logs: $logRoot"
    Write-Host 'Cliente: http://localhost:5174 | Admin: http://localhost:5173'
    Write-Host 'Mission Planner continua responsavel por COM/forwarding quando esse modo estiver configurado.'
    Write-Host 'CTRL+C encerra a supervisao; nao mata aplicativos existentes nem envia comandos ao drone.'
    while ($true) {
        if (-not (Test-ProjectGateway) -and ($null -eq $gatewayChild -or $gatewayChild.HasExited)) {
            $gatewayChild = Start-ObservedChild 'gateway' (Join-Path $PSScriptRoot 'start_gateway.ps1') '-ObserveOnly'
            Write-Host 'Gateway iniciado em observacao: reconexao habilitada, upload/ARM/START bloqueados.'
        }
        $listener = Get-NetTCPConnection -State Listen -LocalPort 5174 -ErrorAction SilentlyContinue
        if ($listener) {
            $page = $null
            try { $page = Invoke-WebRequest -UseBasicParsing -Uri 'http://127.0.0.1:5174/' -TimeoutSec 5 }
            catch { Write-Warning 'Cliente ainda sem resposta HTTP; nova verificacao no proximo ciclo.' }
            if ($null -ne $page -and $page.Content -notmatch '<title>DEVcore Entregas</title>') {
                throw 'Porta 5174 ocupada por outra aplicacao. Nenhum processo foi encerrado.'
            }
        } elseif ($null -eq $mobileChild -or $mobileChild.HasExited) {
            $extra = '-Device web-server -Port 5174'
            if ($FlutterSdkRoot) { $extra += " -FlutterSdkRoot `"$FlutterSdkRoot`"" }
            $mobileChild = Start-ObservedChild 'mobile' (Join-Path $PSScriptRoot 'start_mobile_web.ps1') $extra
            Write-Host 'Cliente Flutter iniciando; compilacao pode levar alguns instantes.'
        }
        Start-Sleep -Seconds $PollSeconds
    }
} finally {
    if ($ownsMutex) { $mutex.ReleaseMutex() }
    $mutex.Dispose()
}
