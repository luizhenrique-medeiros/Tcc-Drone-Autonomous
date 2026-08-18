function New-AsciiWorkspaceAlias {
    param([Parameter(Mandatory)][string]$Root)

    $resolvedRoot = (Resolve-Path -LiteralPath $Root).Path
    if ($resolvedRoot -notmatch '[^\x00-\x7F]') {
        return [pscustomobject]@{
            Root = $resolvedRoot
            Drive = $null
            Owned = $false
        }
    }

    $aliasRoot = Join-Path ([System.IO.Path]::GetTempPath()) 'devcore-workspace'
    if (Test-Path -LiteralPath $aliasRoot) {
        $alias = Get-Item -LiteralPath $aliasRoot
        if ($alias.LinkType -ne 'Junction' -or $alias.Target -notcontains $resolvedRoot) {
            throw "O alias temporário já existe e aponta para outro local: $aliasRoot"
        }
    }
    else {
        New-Item -ItemType Junction -Path $aliasRoot -Target $resolvedRoot | Out-Null
    }

    return [pscustomobject]@{
        Root = $aliasRoot
        Drive = $null
        Owned = $false
    }
}

function Remove-AsciiWorkspaceAlias {
    param([Parameter(Mandatory)][object]$Alias)

    # A junção validada fica no diretório temporário para ser reutilizada por
    # Gradle/Flutter e nunca é removida enquanto um daemon ainda pode usá-la.
    $null = $Alias
}

function Get-FlutterSdkToolPath {
    [CmdletBinding()]
    param(
        [Parameter(Mandatory)][string]$SdkRoot,
        [Parameter(Mandatory)][ValidateSet('flutter', 'dart')][string]$Tool
    )

    foreach ($fileName in @("$Tool.bat", "$Tool.cmd", "$Tool.exe", $Tool)) {
        $candidate = Join-Path $SdkRoot "bin\$fileName"
        if (Test-Path -LiteralPath $candidate -PathType Leaf) {
            return (Resolve-Path -LiteralPath $candidate).Path
        }
    }

    throw "Flutter SDK invalido: bin\$Tool nao foi encontrado em '$SdkRoot'."
}

function Resolve-ProjectFlutterSdk {
    [CmdletBinding()]
    param(
        [string]$ExplicitFlutterSdkRoot,
        [Parameter(Mandatory)][string]$ProjectRoot,
        [switch]$AllowBundledFlutterSdk,
        [ValidateNotNullOrEmpty()][string]$ExpectedChannel = 'stable',
        [ValidateNotNullOrEmpty()][string]$ExpectedFlutterVersionPattern = '^3\.47\.\d+$',
        [ValidateNotNullOrEmpty()][string]$ExpectedDartVersionPattern = '^3\.13\.\d+$'
    )

    $candidateRoot = $null
    $source = $null

    if (-not [string]::IsNullOrWhiteSpace($ExplicitFlutterSdkRoot)) {
        $candidateRoot = $ExplicitFlutterSdkRoot
        $source = 'parameter'
    }
    elseif (-not [string]::IsNullOrWhiteSpace($env:FLUTTER_ROOT)) {
        $candidateRoot = $env:FLUTTER_ROOT
        $source = 'FLUTTER_ROOT'
    }
    else {
        $pathCommand = Get-Command flutter -All -ErrorAction SilentlyContinue |
            Where-Object { -not [string]::IsNullOrWhiteSpace($_.Path) } |
            Select-Object -First 1
        if ($pathCommand) {
            $candidateRoot = Split-Path -Parent (Split-Path -Parent $pathCommand.Path)
            $source = 'PATH'
        }
        elseif ($AllowBundledFlutterSdk) {
            $candidateRoot = Join-Path $ProjectRoot 'flutter'
            $source = 'workspace (explicit opt-in)'
        }
    }

    if ([string]::IsNullOrWhiteSpace($candidateRoot)) {
        throw ('Flutter SDK nao encontrado. Informe -FlutterSdkRoot, defina FLUTTER_ROOT, ' +
            'adicione flutter ao PATH ou use -AllowBundledFlutterSdk conscientemente.')
    }
    if (-not (Test-Path -LiteralPath $candidateRoot -PathType Container)) {
        throw "Flutter SDK selecionado por $source nao existe: '$candidateRoot'."
    }

    $resolvedRoot = (Resolve-Path -LiteralPath $candidateRoot).Path
    $flutterCommand = Get-FlutterSdkToolPath -SdkRoot $resolvedRoot -Tool flutter
    $dartCommand = Get-FlutterSdkToolPath -SdkRoot $resolvedRoot -Tool dart

    $flutterAnalyticsWasPresent = Test-Path Env:FLUTTER_SUPPRESS_ANALYTICS
    $dartAnalyticsWasPresent = Test-Path Env:DART_SUPPRESS_ANALYTICS
    $previousFlutterAnalytics = $env:FLUTTER_SUPPRESS_ANALYTICS
    $previousDartAnalytics = $env:DART_SUPPRESS_ANALYTICS
    try {
        $env:FLUTTER_SUPPRESS_ANALYTICS = 'true'
        $env:DART_SUPPRESS_ANALYTICS = 'true'
        $machineOutput = @(& $flutterCommand --version --machine 2>&1)
        $machineExitCode = $LASTEXITCODE
    }
    finally {
        if ($flutterAnalyticsWasPresent) {
            $env:FLUTTER_SUPPRESS_ANALYTICS = $previousFlutterAnalytics
        }
        else {
            Remove-Item Env:FLUTTER_SUPPRESS_ANALYTICS -ErrorAction SilentlyContinue
        }
        if ($dartAnalyticsWasPresent) {
            $env:DART_SUPPRESS_ANALYTICS = $previousDartAnalytics
        }
        else {
            Remove-Item Env:DART_SUPPRESS_ANALYTICS -ErrorAction SilentlyContinue
        }
    }

    if ($machineExitCode -ne 0) {
        throw "Nao foi possivel validar o Flutter SDK em '$resolvedRoot' (exit $machineExitCode)."
    }
    $machineJson = ($machineOutput | ForEach-Object { $_.ToString() }) -join [Environment]::NewLine
    try {
        $version = $machineJson | ConvertFrom-Json -ErrorAction Stop
    }
    catch {
        throw "flutter --version --machine nao retornou JSON valido para '$resolvedRoot'."
    }

    $flutterVersion = [string]$version.frameworkVersion
    if ([string]::IsNullOrWhiteSpace($flutterVersion)) {
        $flutterVersion = [string]$version.flutterVersion
    }
    $dartVersion = [string]$version.dartSdkVersion
    $channel = [string]$version.channel
    if ($channel -ne $ExpectedChannel) {
        throw "Canal Flutter incompativel em '$resolvedRoot': esperado '$ExpectedChannel', encontrado '$channel'."
    }
    if ($flutterVersion -notmatch $ExpectedFlutterVersionPattern) {
        throw "Versao Flutter incompativel em '$resolvedRoot': '$flutterVersion' nao corresponde a '$ExpectedFlutterVersionPattern'."
    }
    if ($dartVersion -notmatch $ExpectedDartVersionPattern) {
        throw "Versao Dart incompativel em '$resolvedRoot': '$dartVersion' nao corresponde a '$ExpectedDartVersionPattern'."
    }

    $revision = [string]$version.frameworkRevision
    $shortRevision = $revision
    if ($shortRevision.Length -gt 12) {
        $shortRevision = $shortRevision.Substring(0, 12)
    }
    Write-Host "Flutter SDK: source=$source; root=$resolvedRoot; Flutter=$flutterVersion; Dart=$dartVersion; channel=$channel; revision=$shortRevision"

    return [pscustomobject]@{
        Root = $resolvedRoot
        FlutterCommand = $flutterCommand
        DartCommand = $dartCommand
        Source = $source
        FlutterVersion = $flutterVersion
        DartVersion = $dartVersion
        Channel = $channel
        Revision = $revision
    }
}
