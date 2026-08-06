[CmdletBinding()]
param([switch]$SkipBuilds)

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
$flutterSdkRoot = Join-Path $workspaceAlias.Root 'flutter'
$mobileRoot = Join-Path $workspaceAlias.Root 'mobile'
$flutterCommand = Join-Path $flutterSdkRoot 'bin\flutter.bat'
$dartCommand = Join-Path $flutterSdkRoot 'bin\dart.bat'
if (-not $flutterCommand -or -not (Test-Path $flutterCommand)) { $flutterCommand = (Get-Command flutter -ErrorAction SilentlyContinue).Source }
if (-not $dartCommand -or -not (Test-Path $dartCommand)) { $dartCommand = (Get-Command dart -ErrorAction SilentlyContinue).Source }
if ($flutterCommand -and $dartCommand) {
    if ($flutterSdkRoot) {
        $env:GIT_CONFIG_COUNT = '1'
        $env:GIT_CONFIG_KEY_0 = 'safe.directory'
        $env:GIT_CONFIG_VALUE_0 = $flutterSdkRoot.Replace('\', '/')
    }
    $env:FLUTTER_SUPPRESS_ANALYTICS = 'true'
    $env:DART_SUPPRESS_ANALYTICS = 'true'
    Invoke-Checked 'dart format' $mobileRoot { & $dartCommand format --output=none --set-exit-if-changed lib test }
    Invoke-Checked 'flutter analyze' $mobileRoot { & $flutterCommand analyze }
    Invoke-Checked 'flutter test' $mobileRoot { & $flutterCommand test }
    if (-not $SkipBuilds) {
        Invoke-Checked 'flutter clean' $mobileRoot { & $flutterCommand clean }
        Invoke-Checked 'flutter apk debug' $mobileRoot { & $flutterCommand build apk --debug --dart-define=DEMO_MODE=true }
    }
} else {
    $failures.Add('Flutter/Dart não encontrados')
}
Remove-AsciiWorkspaceAlias $workspaceAlias

Invoke-Checked 'docker compose config' $projectRoot { & docker compose config }

if ($failures.Count -gt 0) {
    Write-Host "`nFalhas:" -ForegroundColor Red
    $failures | ForEach-Object { Write-Host "- $_" }
    exit 1
}

Write-Host "`nTodas as validações executadas passaram." -ForegroundColor Green
