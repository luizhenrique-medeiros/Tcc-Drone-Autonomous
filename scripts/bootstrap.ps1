[CmdletBinding()]
param(
    [string]$FlutterSdkRoot,
    [switch]$AllowBundledFlutterSdk,
    [ValidateNotNullOrEmpty()][string]$ExpectedFlutterChannel = 'stable',
    [ValidateNotNullOrEmpty()][string]$ExpectedFlutterVersionPattern = '^3\.47\.\d+$',
    [ValidateNotNullOrEmpty()][string]$ExpectedDartVersionPattern = '^3\.13\.\d+$'
)

$ErrorActionPreference = 'Stop'
$projectRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
. (Join-Path $PSScriptRoot 'windows_path_alias.ps1')

function Assert-Command([string]$Name) {
    if (-not (Get-Command $Name -ErrorAction SilentlyContinue)) {
        throw "Comando obrigatório não encontrado: $Name"
    }
}

function Assert-NativeSuccess([string]$Step) {
    if ($LASTEXITCODE -ne 0) { throw "$Step falhou com exit code $LASTEXITCODE." }
}

Assert-Command 'python'
Assert-Command 'node'

$pythonVersion = & python -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')"
Assert-NativeSuccess 'Leitura da versão do Python'
if ($pythonVersion -ne '3.13') {
    throw "Python 3.13 é obrigatório; encontrado $pythonVersion."
}

foreach ($component in @('backend', 'drone_gateway')) {
    $componentPath = Join-Path $projectRoot $component
    Push-Location $componentPath
    try {
        if (-not (Test-Path '.venv')) {
            & python -m venv .venv
            Assert-NativeSuccess "Criação do ambiente $component"
        }
        & .\.venv\Scripts\python.exe -m pip install --upgrade pip
        Assert-NativeSuccess "Atualização do pip em $component"
        & .\.venv\Scripts\python.exe -m pip install -e '.[dev]'
        Assert-NativeSuccess "Instalação de $component"
    }
    finally { Pop-Location }
}

Push-Location (Join-Path $projectRoot 'admin_web')
try {
    if (Test-Path 'package-lock.json') { & npm.cmd ci } else { & npm.cmd install }
    Assert-NativeSuccess 'Instalação do painel'
}
finally { Pop-Location }

$workspaceAlias = New-AsciiWorkspaceAlias $projectRoot
$flutterSdk = Resolve-ProjectFlutterSdk `
    -ExplicitFlutterSdkRoot $FlutterSdkRoot `
    -ProjectRoot $projectRoot `
    -AllowBundledFlutterSdk:$AllowBundledFlutterSdk `
    -ExpectedChannel $ExpectedFlutterChannel `
    -ExpectedFlutterVersionPattern $ExpectedFlutterVersionPattern `
    -ExpectedDartVersionPattern $ExpectedDartVersionPattern
$flutterCommand = $flutterSdk.FlutterCommand
Push-Location (Join-Path $workspaceAlias.Root 'mobile')
try {
    $env:GIT_CONFIG_COUNT = '1'
    $env:GIT_CONFIG_KEY_0 = 'safe.directory'
    $env:GIT_CONFIG_VALUE_0 = $flutterSdk.Root.Replace('\', '/')
    $env:FLUTTER_SUPPRESS_ANALYTICS = 'true'
    $env:DART_SUPPRESS_ANALYTICS = 'true'
    & $flutterCommand pub get
    Assert-NativeSuccess 'Resolução das dependências Flutter'
}
finally {
    Pop-Location
    Remove-AsciiWorkspaceAlias $workspaceAlias
}

Write-Host 'Bootstrap concluído. Copie .env.example para .env e configure segredos antes de iniciar.'
