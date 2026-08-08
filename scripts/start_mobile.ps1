[CmdletBinding()]
param(
    [switch]$Integrated,
    [switch]$MapTilerConfigured,
    [ValidateSet('demo', 'local_web', 'android_emulator', 'android_physical_device', 'demo_network', 'hosted')]
    [Alias('TargetProfile')]
    [string]$Profile,
    [string]$ApiBaseUrl,
    [string]$Device,
    [int]$WebPort = 5174,
    [switch]$AllowInsecureLanHttp,
    [switch]$SkipPubGet
)

$ErrorActionPreference = 'Stop'
$projectRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
. (Join-Path $PSScriptRoot 'windows_path_alias.ps1')

function Import-ProjectEnvValue {
    param([string]$Name)

    if (-not [string]::IsNullOrWhiteSpace((Get-Item -Path "Env:$Name" -ErrorAction SilentlyContinue).Value)) {
        return
    }
    $envFile = Join-Path $projectRoot '.env'
    if (-not (Test-Path $envFile)) { return }
    foreach ($line in Get-Content -Path $envFile) {
        if ($line -notmatch "^\s*$([Regex]::Escape($Name))\s*=\s*(.*)$") { continue }
        $value = $Matches[1].Trim()
        if ($value.Length -ge 2 -and (($value.StartsWith('"') -and $value.EndsWith('"')) -or ($value.StartsWith("'") -and $value.EndsWith("'")))) {
            $value = $value.Substring(1, $value.Length - 2)
        }
        Set-Item -Path "Env:$Name" -Value $value
        return
    }
}

Import-ProjectEnvValue -Name 'MAPTILER_ANDROID_API_KEY'
Import-ProjectEnvValue -Name 'MAPTILER_WEB_API_KEY'
Import-ProjectEnvValue -Name 'MAPTILER_STYLE_URL'

if ([string]::IsNullOrWhiteSpace($Profile)) {
    if ($env:MOBILE_APP_ENVIRONMENT) {
        $Profile = $env:MOBILE_APP_ENVIRONMENT
    }
    elseif ($Integrated) {
        $Profile = 'android_emulator'
    }
    else {
        $Profile = 'demo'
    }
}

$profileDefaults = @{
    demo = 'http://10.0.2.2:8000'
    local_web = 'http://localhost:8000'
    android_emulator = 'http://10.0.2.2:8000'
}
if ([string]::IsNullOrWhiteSpace($ApiBaseUrl)) {
    if ($profileDefaults.ContainsKey($Profile)) {
        $ApiBaseUrl = $profileDefaults[$Profile]
    }
    elseif ($env:MOBILE_API_BASE_URL) {
        $ApiBaseUrl = $env:MOBILE_API_BASE_URL
    }
    else {
        throw "O perfil '$Profile' exige -ApiBaseUrl. Use o IP da máquina na LAN ou uma URL HTTPS hospedada."
    }
}

$apiUri = $null
if (-not [Uri]::TryCreate($ApiBaseUrl, [UriKind]::Absolute, [ref]$apiUri) -or $apiUri.Scheme -notin @('http', 'https')) {
    throw "ApiBaseUrl inválida: '$ApiBaseUrl'. Informe uma URL HTTP ou HTTPS absoluta."
}
if ($Profile -eq 'hosted' -and $apiUri.Scheme -ne 'https') {
    throw 'O perfil hosted exige uma API HTTPS.'
}
if ($Profile -in @('android_physical_device', 'demo_network') -and $apiUri.Host -in @('localhost', '127.0.0.1', '10.0.2.2')) {
    throw "O perfil '$Profile' exige o IP alcançável do computador na rede; localhost/10.0.2.2 não servem para celular físico."
}

$integratedMode = $Integrated -or $Profile -ne 'demo'
$demoValue = if ($integratedMode) { 'false' } else { 'true' }
$allowLanHttp = $AllowInsecureLanHttp -or $env:MOBILE_ALLOW_INSECURE_LAN_HTTP -eq 'true'
if ($Profile -in @('android_physical_device', 'demo_network') -and $apiUri.Scheme -eq 'http' -and -not $allowLanHttp) {
    throw "HTTP em rede local exige -AllowInsecureLanHttp. Prefira HTTPS sempre que possível."
}
$flutterArgs = @(
    'run',
    "--dart-define=APP_ENVIRONMENT=$Profile",
    "--dart-define=DEMO_MODE=$demoValue",
    "--dart-define=API_BASE_URL=$ApiBaseUrl",
    "--dart-define=ALLOW_INSECURE_LAN_HTTP=$($allowLanHttp.ToString().ToLowerInvariant())"
)

if ($integratedMode) {
    $flutterArgs += '--dart-define=MAP_PROVIDER=maptiler'
    $mapsConfiguredValue = if ($MapTilerConfigured) { 'true' } else { 'false' }
    $flutterArgs += "--dart-define=MAPTILER_CONFIGURED=$mapsConfiguredValue"
}

$isWebTarget = $Profile -eq 'local_web' -or $Device -in @('chrome', 'edge', 'web-server')
if ($MapTilerConfigured) {
    if (-not [string]::IsNullOrWhiteSpace($env:MAPTILER_STYLE_URL)) {
        $flutterArgs += "--dart-define=MAPTILER_STYLE_URL=$($env:MAPTILER_STYLE_URL)"
    }
    if ($isWebTarget) {
        if ([string]::IsNullOrWhiteSpace($env:MAPTILER_WEB_API_KEY)) {
            throw 'MapTilerConfigured no Web exige MAPTILER_WEB_API_KEY no ambiente.'
        }
        $flutterArgs += "--dart-define=MAPTILER_WEB_API_KEY=$($env:MAPTILER_WEB_API_KEY)"
    }
    elseif ([string]::IsNullOrWhiteSpace($env:MAPTILER_ANDROID_API_KEY)) {
        throw 'MapTilerConfigured no Android exige MAPTILER_ANDROID_API_KEY no ambiente.'
    }
    else {
        $flutterArgs += "--dart-define=MAPTILER_ANDROID_API_KEY=$($env:MAPTILER_ANDROID_API_KEY)"
    }
}

if ([string]::IsNullOrWhiteSpace($Device) -and $Profile -eq 'local_web') {
    $Device = 'chrome'
}
if (-not [string]::IsNullOrWhiteSpace($Device)) {
    $flutterArgs += @('-d', $Device)
}
if ($isWebTarget) {
    $flutterArgs += "--web-port=$WebPort"
}

$workspaceAlias = New-AsciiWorkspaceAlias $projectRoot
$flutterSdkRoot = Join-Path $workspaceAlias.Root 'flutter'
$flutterCommand = Join-Path $flutterSdkRoot 'bin\flutter.bat'
if (-not (Test-Path $flutterCommand)) {
    $flutterCommand = (Get-Command flutter -ErrorAction Stop).Source
    $flutterSdkRoot = $null
}
Push-Location (Join-Path $workspaceAlias.Root 'mobile')
$debugVariableWasPresent = Test-Path Env:DEBUG
$previousDebugValue = $env:DEBUG
# O wrapper Gradle ativa echo quando DEBUG possui qualquer valor e pode então
# imprimir os --dart-define codificados. As chaves de cliente continuam
# públicas no bundle, mas não devem aparecer desnecessariamente no terminal.
$env:DEBUG = ''
try {
    if ($flutterSdkRoot) {
        $env:GIT_CONFIG_COUNT = '1'
        $env:GIT_CONFIG_KEY_0 = 'safe.directory'
        $env:GIT_CONFIG_VALUE_0 = $flutterSdkRoot.Replace('\', '/')
    }
    $env:FLUTTER_SUPPRESS_ANALYTICS = 'true'
    $env:DART_SUPPRESS_ANALYTICS = 'true'
    $packageConfig = Join-Path (Get-Location) '.dart_tool\package_config.json'
    $pubspec = Join-Path (Get-Location) 'pubspec.yaml'
    $lockfile = Join-Path (Get-Location) 'pubspec.lock'
    $dependenciesChanged = -not (Test-Path $packageConfig)
    if (-not $dependenciesChanged) {
        $packageConfigTime = (Get-Item $packageConfig).LastWriteTimeUtc
        $dependenciesChanged = (Get-Item $pubspec).LastWriteTimeUtc -gt $packageConfigTime
        if (Test-Path $lockfile) {
            $dependenciesChanged = $dependenciesChanged -or (Get-Item $lockfile).LastWriteTimeUtc -gt $packageConfigTime
        }
    }
    if (-not $SkipPubGet -and $dependenciesChanged) {
        Write-Host 'Dependências Flutter alteradas; executando flutter pub get...'
        & $flutterCommand pub get
        if ($LASTEXITCODE -ne 0) { throw "flutter pub get encerrou com exit code $LASTEXITCODE." }
    }
    if ($isWebTarget) {
        Write-Host ''
        Write-Host 'Aplicativo Flutter Web:'
        Write-Host "http://localhost:$WebPort"
        Write-Host 'Hot reload: pressione r no terminal do Flutter.'
        Write-Host "Backend: $ApiBaseUrl"
        Write-Host "MapTiler Web configurado: $($MapTilerConfigured.IsPresent)"
        Write-Host ''
    }
    & $flutterCommand @flutterArgs
    if ($LASTEXITCODE -ne 0) { throw "Flutter encerrou com exit code $LASTEXITCODE." }
}
finally {
    if ($debugVariableWasPresent) {
        $env:DEBUG = $previousDebugValue
    }
    else {
        Remove-Item Env:DEBUG -ErrorAction SilentlyContinue
    }
    Pop-Location
    Remove-AsciiWorkspaceAlias $workspaceAlias
}
