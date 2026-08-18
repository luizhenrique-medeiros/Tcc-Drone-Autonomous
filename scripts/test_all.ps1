[CmdletBinding()]
param(
    [switch]$SkipBuilds,
    [switch]$SkipWebBuild,
    [switch]$BuildReleaseApk,
    [string]$FlutterSdkRoot,
    [switch]$AllowBundledFlutterSdk,
    [ValidateNotNullOrEmpty()][string]$ExpectedFlutterChannel = 'stable',
    [ValidateNotNullOrEmpty()][string]$ExpectedFlutterVersionPattern = '^3\.47\.\d+$',
    [ValidateNotNullOrEmpty()][string]$ExpectedDartVersionPattern = '^3\.13\.\d+$'
)

$ErrorActionPreference = 'Continue'
$projectRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
. (Join-Path $PSScriptRoot 'windows_path_alias.ps1')
$failures = [System.Collections.Generic.List[string]]::new()

function Invoke-Checked([string]$Name, [string]$WorkingDirectory, [scriptblock]$Command) {
    Write-Host "`n[$Name]" -ForegroundColor Cyan
    Push-Location $WorkingDirectory
    try {
        & $Command
        if ($LASTEXITCODE -ne 0) { $failures.Add("$Name (exit $LASTEXITCODE)") }
    }
    catch {
        Write-Error $_
        $failures.Add("$Name ($($_.Exception.Message))")
    }
    finally { Pop-Location }
}

$backendPython = Join-Path $projectRoot 'backend\.venv\Scripts\python.exe'
if (-not (Test-Path $backendPython)) { $backendPython = 'python' }
Invoke-Checked 'backend ruff' (Join-Path $projectRoot 'backend') { & $backendPython -m ruff check . }
Invoke-Checked 'backend format' (Join-Path $projectRoot 'backend') { & $backendPython -m ruff format --check . }
Invoke-Checked 'backend pytest' (Join-Path $projectRoot 'backend') { & $backendPython -m pytest }

$gatewayPython = Join-Path $projectRoot 'drone_gateway\.venv\Scripts\python.exe'
if (-not (Test-Path $gatewayPython)) { $gatewayPython = 'python' }
Invoke-Checked 'gateway ruff' (Join-Path $projectRoot 'drone_gateway') { & $gatewayPython -m ruff check . }
Invoke-Checked 'gateway format' (Join-Path $projectRoot 'drone_gateway') { & $gatewayPython -m ruff format --check . }
Invoke-Checked 'gateway pytest' (Join-Path $projectRoot 'drone_gateway') { & $gatewayPython -m pytest }

Invoke-Checked 'admin lint' (Join-Path $projectRoot 'admin_web') { & npm.cmd run lint }
Invoke-Checked 'admin test' (Join-Path $projectRoot 'admin_web') { & npm.cmd run test }
if (-not $SkipBuilds) { Invoke-Checked 'admin build' (Join-Path $projectRoot 'admin_web') { & npm.cmd run build } }

$workspaceAlias = New-AsciiWorkspaceAlias $projectRoot
$mobileRoot = Join-Path $workspaceAlias.Root 'mobile'
$flutterSdk = $null
try {
    $flutterSdk = Resolve-ProjectFlutterSdk `
        -ExplicitFlutterSdkRoot $FlutterSdkRoot `
        -ProjectRoot $projectRoot `
        -AllowBundledFlutterSdk:$AllowBundledFlutterSdk `
        -ExpectedChannel $ExpectedFlutterChannel `
        -ExpectedFlutterVersionPattern $ExpectedFlutterVersionPattern `
        -ExpectedDartVersionPattern $ExpectedDartVersionPattern
}
catch {
    Write-Error $_
    $failures.Add("Flutter SDK ($($_.Exception.Message))")
}
if ($flutterSdk) {
    $flutterCommand = $flutterSdk.FlutterCommand
    $dartCommand = $flutterSdk.DartCommand
    $env:GIT_CONFIG_COUNT = '1'
    $env:GIT_CONFIG_KEY_0 = 'safe.directory'
    $env:GIT_CONFIG_VALUE_0 = $flutterSdk.Root.Replace('\', '/')
    $env:FLUTTER_SUPPRESS_ANALYTICS = 'true'
    $env:DART_SUPPRESS_ANALYTICS = 'true'
    Invoke-Checked 'flutter pub get' $mobileRoot { & $flutterCommand pub get }
    Invoke-Checked 'dart format' $mobileRoot { & $dartCommand format --output=none --set-exit-if-changed lib test }
    Invoke-Checked 'flutter analyze' $mobileRoot { & $flutterCommand analyze }
    Invoke-Checked 'flutter test' $mobileRoot { & $flutterCommand test }
    if (-not $SkipBuilds) {
        Invoke-Checked 'flutter clean' $mobileRoot { & $flutterCommand clean }
        if (-not $SkipWebBuild) {
            Invoke-Checked 'flutter web release' $mobileRoot {
                & $flutterCommand build web --release `
                    --dart-define=APP_ENVIRONMENT=local_web `
                    --dart-define=DEMO_MODE=true `
                    --dart-define=MAPTILER_CONFIGURED=false
            }
        }
        Invoke-Checked 'flutter apk debug' $mobileRoot { & $flutterCommand build apk --debug --dart-define=DEMO_MODE=true }
        if ($BuildReleaseApk) {
            Invoke-Checked 'flutter apk release' $mobileRoot { & $flutterCommand build apk --release --dart-define=DEMO_MODE=true }
        }
    }
}
Remove-AsciiWorkspaceAlias $workspaceAlias

Invoke-Checked 'docker compose config' $projectRoot { & docker compose config --quiet }

if ($failures.Count -gt 0) {
    Write-Host "`nFalhas:" -ForegroundColor Red
    $failures | ForEach-Object { Write-Host "- $_" }
    exit 1
}

Write-Host "`nTodas as validações executadas passaram." -ForegroundColor Green
