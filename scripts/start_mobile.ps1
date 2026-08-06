[CmdletBinding()]
param(
    [switch]$Integrated,
    [switch]$GoogleMapsConfigured,
    [string]$ApiBaseUrl
)

$ErrorActionPreference = 'Stop'
$projectRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
. (Join-Path $PSScriptRoot 'windows_path_alias.ps1')
if ([string]::IsNullOrWhiteSpace($ApiBaseUrl)) {
    $ApiBaseUrl = if ($env:MOBILE_API_BASE_URL) { $env:MOBILE_API_BASE_URL } else { 'http://10.0.2.2:8000' }
}
$demoValue = if ($Integrated) { 'false' } else { 'true' }
$flutterArgs = @('run', "--dart-define=DEMO_MODE=$demoValue")
if ($Integrated) {
    $flutterArgs += "--dart-define=API_BASE_URL=$ApiBaseUrl"
    $flutterArgs += '--dart-define=MAP_PROVIDER=google_maps'
    $mapsConfiguredValue = if ($GoogleMapsConfigured) { 'true' } else { 'false' }
    if ($GoogleMapsConfigured -and [string]::IsNullOrWhiteSpace($env:GOOGLE_MAPS_ANDROID_API_KEY)) {
        throw 'GoogleMapsConfigured exige GOOGLE_MAPS_ANDROID_API_KEY no ambiente.'
    }
    $flutterArgs += "--dart-define=GOOGLE_MAPS_CONFIGURED=$mapsConfiguredValue"
}
$workspaceAlias = New-AsciiWorkspaceAlias $projectRoot
$flutterSdkRoot = Join-Path $workspaceAlias.Root 'flutter'
$flutterCommand = Join-Path $flutterSdkRoot 'bin\flutter.bat'
if (-not (Test-Path $flutterCommand)) {
    $flutterCommand = (Get-Command flutter -ErrorAction Stop).Source
    $flutterSdkRoot = $null
}
Push-Location (Join-Path $workspaceAlias.Root 'mobile')
try {
    if ($flutterSdkRoot) {
        $env:GIT_CONFIG_COUNT = '1'
        $env:GIT_CONFIG_KEY_0 = 'safe.directory'
        $env:GIT_CONFIG_VALUE_0 = $flutterSdkRoot.Replace('\', '/')
    }
    $env:FLUTTER_SUPPRESS_ANALYTICS = 'true'
    $env:DART_SUPPRESS_ANALYTICS = 'true'
    & $flutterCommand @flutterArgs
    if ($LASTEXITCODE -ne 0) { throw "Flutter encerrou com exit code $LASTEXITCODE." }
}
finally {
    Pop-Location
    Remove-AsciiWorkspaceAlias $workspaceAlias
}
