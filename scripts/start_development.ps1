[CmdletBinding()]
param(
    [ValidateSet('chrome', 'edge', 'web-server')]
    [string]$Device = 'chrome',
    [ValidateRange(1, 65535)]
    [int]$FlutterWebPort = 5174,
    [ValidateNotNullOrEmpty()]
    [string]$ApiBaseUrl = 'http://localhost:8000',
    [switch]$WithoutMapTiler,
    [switch]$SkipPubGet,
    [string]$FlutterSdkRoot,
    [switch]$AllowBundledFlutterSdk,
    [ValidateNotNullOrEmpty()][string]$ExpectedFlutterChannel = 'stable',
    [ValidateNotNullOrEmpty()][string]$ExpectedFlutterVersionPattern = '^3\.47\.\d+$',
    [ValidateNotNullOrEmpty()][string]$ExpectedDartVersionPattern = '^3\.13\.\d+$',
    [switch]$SkipDockerBuild,
    [switch]$IncludeSimulationGateway,
    [switch]$ConfirmSimulationGateway,
    [ValidateRange(10, 600)]
    [int]$ReadinessTimeoutSeconds = 120,
    [switch]$ValidateOnly
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
$projectRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$envFile = Join-Path $projectRoot '.env'
$mobileLauncher = Join-Path $PSScriptRoot 'start_mobile_web.ps1'
$pathHelpers = Join-Path $PSScriptRoot 'windows_path_alias.ps1'

function Assert-NativeSuccess {
    param([Parameter(Mandatory = $true)][string]$Step)

    if ($LASTEXITCODE -ne 0) {
        throw "$Step falhou com exit code $LASTEXITCODE."
    }
}

function Assert-CommandAvailable {
    param([Parameter(Mandatory = $true)][string]$Name)

    if (-not (Get-Command $Name -ErrorAction SilentlyContinue)) {
        throw "Comando obrigatorio nao encontrado: $Name"
    }
}

function Invoke-DockerChecked {
    param(
        [Parameter(Mandatory = $true)][string[]]$Arguments,
        [Parameter(Mandatory = $true)][string]$Step
    )

    & docker @Arguments
    Assert-NativeSuccess -Step $Step
}

function Get-ComposeContainerId {
    param([Parameter(Mandatory = $true)][string]$Service)

    $output = @(& docker compose --profile gateway ps -q $Service 2>$null)
    Assert-NativeSuccess -Step "Consulta do container $Service"
    return (($output | ForEach-Object { $_.ToString().Trim() } | Where-Object { $_ }) -join '')
}

function Get-ContainerState {
    param([Parameter(Mandatory = $true)][string]$ContainerId)

    $stateJson = (@(& docker inspect --format '{{json .State}}' $ContainerId 2>$null) -join '')
    Assert-NativeSuccess -Step 'Inspecao do estado do container'
    try {
        return $stateJson | ConvertFrom-Json -ErrorAction Stop
    }
    catch {
        throw 'O Docker retornou um estado de container invalido.'
    }
}

function Wait-ComposeService {
    param(
        [Parameter(Mandatory = $true)][string]$Service,
        [Parameter(Mandatory = $true)][int]$TimeoutSeconds,
        [switch]$RequireHealthy
    )

    $deadline = [DateTime]::UtcNow.AddSeconds($TimeoutSeconds)
    do {
        $containerId = Get-ComposeContainerId -Service $Service
        if (-not [string]::IsNullOrWhiteSpace($containerId)) {
            $state = Get-ContainerState -ContainerId $containerId
            if ($state.Status -in @('dead', 'exited')) {
                throw "O servico Docker '$Service' encerrou durante a inicializacao. Consulte: docker compose logs $Service"
            }
            if ($state.Status -eq 'running') {
                if (-not $RequireHealthy) {
                    return
                }
                if ($null -ne $state.Health -and $state.Health.Status -eq 'healthy') {
                    return
                }
            }
        }
        Start-Sleep -Seconds 2
    } while ([DateTime]::UtcNow -lt $deadline)

    $expectedState = if ($RequireHealthy) { 'healthy' } else { 'running' }
    throw "Timeout aguardando o servico Docker '$Service' ficar $expectedState."
}

function Wait-HttpReady {
    param(
        [Parameter(Mandatory = $true)][string]$Name,
        [Parameter(Mandatory = $true)][string]$Url,
        [Parameter(Mandatory = $true)][int]$TimeoutSeconds
    )

    $deadline = [DateTime]::UtcNow.AddSeconds($TimeoutSeconds)
    do {
        try {
            $response = Invoke-WebRequest -UseBasicParsing -Uri $Url -TimeoutSec 5
            if ($response.StatusCode -eq 200) {
                return
            }
        }
        catch {
            # A dependencia ainda pode estar no periodo normal de inicializacao.
        }
        Start-Sleep -Seconds 2
    } while ([DateTime]::UtcNow -lt $deadline)

    throw "Timeout aguardando $Name responder HTTP 200 em $Url."
}

function Assert-GatewayComposeSafety {
    $configOutput = @(& docker compose --profile gateway config --format json 2>$null)
    Assert-NativeSuccess -Step 'Validacao da topologia Docker do gateway'
    try {
        $config = (($configOutput | ForEach-Object { $_.ToString() }) -join [Environment]::NewLine) |
            ConvertFrom-Json -ErrorAction Stop
    }
    catch {
        throw 'Nao foi possivel validar a configuracao efetiva do gateway Docker.'
    }

    $gatewayEnvironment = $config.services.gateway.environment
    $expected = @{
        GATEWAY_RUNTIME = 'container'
        MAVLINK_MODE = 'simulation'
        MAVLINK_CONNECTION = 'udp:0.0.0.0:14550'
        REAL_HARDWARE_ACKNOWLEDGED = 'false'
        ALLOW_MISSION_UPLOAD = 'false'
        ALLOW_FLIGHT_COMMANDS = 'false'
        ALLOW_MISSION_START = 'false'
        ALLOW_VEHICLE_ARM = 'false'
    }
    foreach ($name in $expected.Keys) {
        $property = $gatewayEnvironment.PSObject.Properties[$name]
        if ($null -eq $property -or [string]$property.Value -ne $expected[$name]) {
            throw "Topologia insegura recusada: o gateway Docker exige $name=$($expected[$name])."
        }
    }
}

if ($IncludeSimulationGateway -and -not $ConfirmSimulationGateway) {
    throw 'Para iniciar o gateway Docker simulado, informe tambem -ConfirmSimulationGateway.'
}
if ($ConfirmSimulationGateway -and -not $IncludeSimulationGateway) {
    throw '-ConfirmSimulationGateway so pode ser usado junto de -IncludeSimulationGateway.'
}

$apiUri = $null
if (-not [Uri]::TryCreate($ApiBaseUrl, [UriKind]::Absolute, [ref]$apiUri) -or
    $apiUri.Scheme -ne 'http' -or
    $apiUri.Host -notin @('localhost', '127.0.0.1') -or
    $apiUri.Port -ne 8000) {
    throw 'Este launcher local exige -ApiBaseUrl http://localhost:8000 (ou http://127.0.0.1:8000).'
}

if (-not (Test-Path -LiteralPath $envFile -PathType Leaf)) {
    throw 'Arquivo .env ausente. Copie .env.example para .env e configure os valores locais sem versionar segredos.'
}
foreach ($requiredPath in @($mobileLauncher, $pathHelpers, (Join-Path $projectRoot 'compose.yaml'))) {
    if (-not (Test-Path -LiteralPath $requiredPath -PathType Leaf)) {
        throw "Arquivo obrigatorio nao encontrado: $requiredPath"
    }
}

$flutterWebListener = Get-NetTCPConnection -State Listen -LocalPort $FlutterWebPort -ErrorAction SilentlyContinue
if ($flutterWebListener) {
    $processIds = $flutterWebListener.OwningProcess | Sort-Object -Unique
    throw "A porta do Flutter Web $FlutterWebPort ja esta em uso (PID: $($processIds -join ', '))."
}

Assert-CommandAvailable -Name 'docker'
. $pathHelpers

$gatewayOverrides = [ordered]@{
    GATEWAY_RUNTIME = 'container'
    GATEWAY_CONTAINER_MAVLINK_MODE = 'simulation'
    GATEWAY_CONTAINER_MAVLINK_CONNECTION = 'udp:0.0.0.0:14550'
    REAL_HARDWARE_ACKNOWLEDGED = 'false'
    ALLOW_MISSION_UPLOAD = 'false'
    ALLOW_FLIGHT_COMMANDS = 'false'
    ALLOW_MISSION_START = 'false'
    ALLOW_VEHICLE_ARM = 'false'
}
$savedGatewayEnvironment = @{}
$gatewayOverridesApplied = $false

Push-Location $projectRoot
try {
    $dockerServerVersion = (@(& docker info --format '{{.ServerVersion}}' 2>$null) -join '').Trim()
    Assert-NativeSuccess -Step 'Acesso ao Docker Desktop'
    if ([string]::IsNullOrWhiteSpace($dockerServerVersion)) {
        throw 'Docker Desktop respondeu sem informar a versao do daemon.'
    }

    $flutterSdk = Resolve-ProjectFlutterSdk `
        -ExplicitFlutterSdkRoot $FlutterSdkRoot `
        -ProjectRoot $projectRoot `
        -AllowBundledFlutterSdk:$AllowBundledFlutterSdk `
        -ExpectedChannel $ExpectedFlutterChannel `
        -ExpectedFlutterVersionPattern $ExpectedFlutterVersionPattern `
        -ExpectedDartVersionPattern $ExpectedDartVersionPattern

    if ($IncludeSimulationGateway) {
        $gatewayOverridesApplied = $true
        foreach ($name in $gatewayOverrides.Keys) {
            $existing = Get-Item -Path "Env:$name" -ErrorAction SilentlyContinue
            $savedGatewayEnvironment[$name] = [pscustomobject]@{
                Exists = $null -ne $existing
                Value = if ($null -ne $existing) { $existing.Value } else { $null }
            }
            Set-Item -Path "Env:$name" -Value $gatewayOverrides[$name]
        }
    }

    $composeArguments = @('compose')
    if ($IncludeSimulationGateway) {
        $composeArguments += @('--profile', 'gateway')
    }
    Invoke-DockerChecked -Arguments ($composeArguments + @('config', '--quiet')) -Step 'Validacao do Docker Compose'

    $services = @(& docker @($composeArguments + @('config', '--services')))
    Assert-NativeSuccess -Step 'Leitura dos servicos Docker Compose'
    foreach ($requiredService in @('db', 'backend', 'admin')) {
        if ($requiredService -notin $services) {
            throw "Servico obrigatorio ausente no Docker Compose: $requiredService"
        }
    }

    $existingGatewayId = Get-ComposeContainerId -Service 'gateway'
    if (-not [string]::IsNullOrWhiteSpace($existingGatewayId) -and -not $IncludeSimulationGateway) {
        $existingGatewayState = Get-ContainerState -ContainerId $existingGatewayId
        if ($existingGatewayState.Status -eq 'running') {
            throw ('Ja existe um gateway Docker em execucao. Por seguranca, pare-o explicitamente ou execute ' +
                'este launcher com -IncludeSimulationGateway -ConfirmSimulationGateway para recria-lo em simulation.')
        }
    }

    if ($IncludeSimulationGateway) {
        if ('gateway' -notin $services) {
            throw 'O profile gateway nao disponibilizou o servico Docker esperado.'
        }
        Assert-GatewayComposeSafety
    }

    if ($ValidateOnly) {
        Write-Host "Validacao concluida: Docker $dockerServerVersion, Compose valido e Flutter $($flutterSdk.FlutterVersion)."
        Write-Host 'Nenhum container ou processo da aplicacao foi iniciado.'
        if ($IncludeSimulationGateway) {
            Write-Host 'Gateway validado: Docker simulation, runtime container e todos os gates de mutacao bloqueados.'
        }
        else {
            Write-Host 'Gateway: nao sera iniciado.'
        }
        return
    }

    $upArguments = $composeArguments + @('up', '-d')
    if (-not $SkipDockerBuild) {
        $upArguments += '--build'
    }
    $upArguments += @('db', 'backend', 'admin')
    if ($IncludeSimulationGateway) {
        $upArguments += 'gateway'
    }
    Invoke-DockerChecked -Arguments $upArguments -Step 'Inicializacao da pilha Docker local'

    Wait-ComposeService -Service 'db' -TimeoutSeconds $ReadinessTimeoutSeconds -RequireHealthy
    Wait-ComposeService -Service 'backend' -TimeoutSeconds $ReadinessTimeoutSeconds -RequireHealthy
    Wait-ComposeService -Service 'admin' -TimeoutSeconds $ReadinessTimeoutSeconds
    Wait-HttpReady -Name 'backend' -Url 'http://127.0.0.1:8000/ready' -TimeoutSeconds $ReadinessTimeoutSeconds
    Wait-HttpReady -Name 'painel administrativo' -Url 'http://127.0.0.1:5173/' -TimeoutSeconds $ReadinessTimeoutSeconds
    if ($IncludeSimulationGateway) {
        Wait-ComposeService -Service 'gateway' -TimeoutSeconds $ReadinessTimeoutSeconds
    }

    Write-Host ''
    Write-Host 'Ambiente Docker pronto:'
    Write-Host 'Banco: OK (PostgreSQL/PostGIS healthy)'
    Write-Host 'Backend: OK - http://localhost:8000'
    Write-Host 'Admin Web: OK - http://localhost:5173'
    if ($IncludeSimulationGateway) {
        Write-Host 'Gateway: OK em SIMULATION no Docker; hardware real nao foi iniciado.'
    }
    else {
        Write-Host 'Gateway: NAO INICIADO (padrao seguro).'
        Write-Host 'COM7/forwarding: use scripts/start_gateway.ps1 no host, em outro terminal.'
    }
    Write-Host "Flutter Web: iniciando em primeiro plano - http://localhost:$FlutterWebPort"
    Write-Host 'Ao encerrar o Flutter, os containers Docker permanecem ativos.'
    Write-Host ''

    $mobileParameters = @{
        Device = $Device
        Port = $FlutterWebPort
        ApiBaseUrl = $ApiBaseUrl
        WithoutMapTiler = $WithoutMapTiler
        SkipPubGet = $SkipPubGet
        FlutterSdkRoot = $flutterSdk.Root
        AllowBundledFlutterSdk = $AllowBundledFlutterSdk
        ExpectedFlutterChannel = $ExpectedFlutterChannel
        ExpectedFlutterVersionPattern = $ExpectedFlutterVersionPattern
        ExpectedDartVersionPattern = $ExpectedDartVersionPattern
    }
    & $mobileLauncher @mobileParameters
}
finally {
    if ($gatewayOverridesApplied) {
        foreach ($name in $savedGatewayEnvironment.Keys) {
            $saved = $savedGatewayEnvironment[$name]
            if ($saved.Exists) {
                Set-Item -Path "Env:$name" -Value $saved.Value
            }
            else {
                Remove-Item -Path "Env:$name" -ErrorAction SilentlyContinue
            }
        }
    }
    Pop-Location
}
