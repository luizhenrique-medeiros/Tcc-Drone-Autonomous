[CmdletBinding()]
param(
    [ValidateSet('chrome', 'edge', 'web-server')]
    [string]$Device = 'chrome',
    [int]$Port = 0,
    [string]$ApiBaseUrl = 'http://localhost:8000',
    [switch]$WithoutMapTiler,
    [switch]$SkipPubGet,
    [string]$FlutterSdkRoot,
    [switch]$AllowBundledFlutterSdk,
    [ValidateNotNullOrEmpty()][string]$ExpectedFlutterChannel = 'stable',
    [ValidateNotNullOrEmpty()][string]$ExpectedFlutterVersionPattern = '^3\.47\.\d+$',
    [ValidateNotNullOrEmpty()][string]$ExpectedDartVersionPattern = '^3\.13\.\d+$'
)

$ErrorActionPreference = 'Stop'
$projectRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$envFile = Join-Path $projectRoot '.env'

function Import-DotEnvValue {
    param(
        [Parameter(Mandatory = $true)][string]$Path,
        [Parameter(Mandatory = $true)][string]$Name
    )

    if (-not (Test-Path $Path) -or -not [string]::IsNullOrWhiteSpace((Get-Item -Path "Env:$Name" -ErrorAction SilentlyContinue).Value)) {
        return
    }
    foreach ($line in Get-Content -Path $Path) {
        if ($line -notmatch "^\s*$([Regex]::Escape($Name))\s*=\s*(.*)$") { continue }
        $value = $Matches[1].Trim()
        if ($value.Length -ge 2 -and (($value.StartsWith('"') -and $value.EndsWith('"')) -or ($value.StartsWith("'") -and $value.EndsWith("'")))) {
            $value = $value.Substring(1, $value.Length - 2)
        }
        Set-Item -Path "Env:$Name" -Value $value
        return
    }
}

Import-DotEnvValue -Path $envFile -Name 'MAPTILER_WEB_API_KEY'
Import-DotEnvValue -Path $envFile -Name 'MAPTILER_STYLE_URL'
Import-DotEnvValue -Path $envFile -Name 'FLUTTER_WEB_PORT'

if ($Port -le 0) {
    $configuredPort = 0
    if (-not [int]::TryParse($env:FLUTTER_WEB_PORT, [ref]$configuredPort) -or $configuredPort -le 0) {
        $configuredPort = 5174
    }
    $Port = $configuredPort
}

$listeningConnection = Get-NetTCPConnection -State Listen -LocalPort $Port -ErrorAction SilentlyContinue
if ($listeningConnection) {
    $processIds = $listeningConnection.OwningProcess | Sort-Object -Unique
    throw "A porta $Port já está em uso (PID: $($processIds -join ', ')). Encerre o processo ou informe -Port outra_porta."
}

$mapsConfigured = -not $WithoutMapTiler -and -not [string]::IsNullOrWhiteSpace($env:MAPTILER_WEB_API_KEY)
if (-not $mapsConfigured) {
    Write-Warning 'MAPTILER_WEB_API_KEY não encontrada; o app abrirá com diagnóstico explícito e mapa local de desenvolvimento.'
}

$startParameters = @{
    Integrated = $true
    Profile = 'local_web'
    ApiBaseUrl = $ApiBaseUrl
    Device = $Device
    WebPort = $Port
    SkipPubGet = $SkipPubGet
    FlutterSdkRoot = $FlutterSdkRoot
    AllowBundledFlutterSdk = $AllowBundledFlutterSdk
    ExpectedFlutterChannel = $ExpectedFlutterChannel
    ExpectedFlutterVersionPattern = $ExpectedFlutterVersionPattern
    ExpectedDartVersionPattern = $ExpectedDartVersionPattern
}
if ($mapsConfigured) {
    $startParameters.MapTilerConfigured = $true
}

& (Join-Path $PSScriptRoot 'start_mobile.ps1') @startParameters
if ($LASTEXITCODE -ne 0) {
    throw "start_mobile.ps1 encerrou com exit code $LASTEXITCODE."
}
