[CmdletBinding()]
param(
    [string]$BaseUrl = 'http://127.0.0.1:8000',
    [string]$AdminEmail = 'admin@example.local',
    [string]$AdminPassword = $env:ADMIN_INITIAL_PASSWORD,
    [int]$TimeoutSeconds = 75,
    [switch]$ConfirmSimulationMutation,
    [switch]$AllowNonLocalTarget
)

$ErrorActionPreference = 'Stop'
$targetUri = $null
if (-not [Uri]::TryCreate($BaseUrl, [UriKind]::Absolute, [ref]$targetUri)) {
    throw "BaseUrl inválida: '$BaseUrl'."
}
if (-not $ConfirmSimulationMutation) {
    throw 'Este smoke cria e altera dados. Repita com -ConfirmSimulationMutation somente contra o ambiente local de simulação.'
}
if (-not $AllowNonLocalTarget -and $targetUri.Host -notin @('localhost', '127.0.0.1', '::1')) {
    throw 'Destino não local bloqueado. O smoke não deve ser executado contra demo/produção; -AllowNonLocalTarget exige revisão explícita.'
}
if ([string]::IsNullOrWhiteSpace($AdminPassword) -or $AdminPassword -eq 'change_me') {
    throw 'Informe -AdminPassword ou ADMIN_INITIAL_PASSWORD; a senha padrão não é aceita.'
}
$api = "$($BaseUrl.TrimEnd('/'))/api/v1"

function Invoke-Api {
    param(
        [Parameter(Mandatory)][ValidateSet('GET', 'POST')][string]$Method,
        [Parameter(Mandatory)][string]$Path,
        [hashtable]$Headers = @{},
        [object]$Body
    )

    $request = @{
        Method = $Method
        Uri = "$api$Path"
        Headers = $Headers
        ErrorAction = 'Stop'
    }
    if ($null -ne $Body) {
        $request.ContentType = 'application/json'
        $request.Body = $Body | ConvertTo-Json -Depth 10 -Compress
    }

    try {
        return Invoke-RestMethod @request
    }
    catch {
        $responseBody = $_.ErrorDetails.Message
        if (-not $responseBody) { $responseBody = $_.Exception.Message }
        throw "$Method $Path falhou: $responseBody"
    }
}

function Assert-Value {
    param([string]$Label, [object]$Actual, [object]$Expected)
    if ($Actual -ne $Expected) {
        throw "$Label esperado '$Expected', recebido '$Actual'."
    }
}

$suffix = "$(Get-Date -Format 'yyyyMMddHHmmss')-$([guid]::NewGuid().ToString('N').Substring(0, 8))"
$customerEmail = "smoke-$suffix@example.local"
$customerPassword = 'Customer-pass-123'

$registered = Invoke-Api POST '/auth/register' -Body @{
    name = 'Cliente Smoke'
    email = $customerEmail
    phone = '+5511999999999'
    password = $customerPassword
    role = 'ADMIN'
}
Assert-Value 'papel do cadastro público' $registered.role 'CUSTOMER'

$customerLogin = Invoke-Api POST '/auth/login' -Body @{
    email = $customerEmail
    password = $customerPassword
}
$adminLogin = Invoke-Api POST '/auth/login' -Body @{
    email = $AdminEmail
    password = $AdminPassword
}
$customerHeaders = @{ Authorization = "Bearer $($customerLogin.access_token)" }
$adminHeaders = @{ Authorization = "Bearer $($adminLogin.access_token)" }

$products = Invoke-Api GET '/products' -Headers $customerHeaders
if ($products.Count -lt 1) { throw 'O catálogo semeado está vazio.' }

$pointHeaders = $customerHeaders.Clone()
$pointHeaders['Idempotency-Key'] = "point-$suffix"
$point = Invoke-Api POST '/delivery-points' -Headers $pointHeaders -Body @{
    searched_address = 'Base acadêmica'
    address_reference = 'Área aberta próxima à base'
    selection_source = 'ADDRESS_SEARCH'
    approximate_latitude = -23.1175
    approximate_longitude = -46.5502
    final_latitude = -23.1170
    final_longitude = -46.5500
    label = 'Ponto exato do smoke test'
    instructions = 'Simulação: usar o centro da área isolada.'
    map_provider = 'maptiler'
    map_type = 'satellite'
    accuracy_meters = 3
    region_confirmed = $true
    exact_point_selected = $true
    user_confirmed = $true
    user_confirmed_safe_area = $true
}

$orderHeaders = $customerHeaders.Clone()
$orderHeaders['Idempotency-Key'] = "order-$suffix"
$order = Invoke-Api POST '/orders' -Headers $orderHeaders -Body @{
    delivery_point_id = $point.id
    payment_method = 'PIX'
    items = @(@{ product_id = $products[0].id; quantity = 1 })
}
Assert-Value 'estado inicial do pedido' $order.status 'DRAFT'

$submitHeaders = $customerHeaders.Clone()
$submitHeaders['Idempotency-Key'] = "submit-$suffix"
$order = Invoke-Api POST "/orders/$($order.id)/submit" -Headers $submitHeaders
Assert-Value 'pedido enviado' $order.status 'PENDING_ADMIN_APPROVAL'

$order = Invoke-Api POST "/admin/orders/$($order.id)/approve" -Headers $adminHeaders -Body @{
    reason = 'Área adequada para o smoke test simulado.'
}
Assert-Value 'pedido aprovado' $order.status 'APPROVED'

$mission = Invoke-Api POST "/admin/orders/$($order.id)/prepare-mission" -Headers $adminHeaders
Assert-Value 'missão gerada' $mission.status 'GENERATED'
if (@($mission.waypoints).Count -ne 7) { throw 'A missão não possui os 7 waypoints esperados.' }

$export = Invoke-WebRequest -UseBasicParsing -Method Get -Uri "$api/admin/missions/$($mission.id)/export" -Headers $adminHeaders
if (-not $export.Content.StartsWith("QGC WPL 110`n")) { throw 'Exportação não está no formato QGC WPL 110.' }
Assert-Value 'hash exportado' $export.Headers['X-Mission-SHA256'] $mission.mission_sha256

$mission = Invoke-Api POST "/admin/missions/$($mission.id)/mark-under-review" -Headers $adminHeaders
$mission = Invoke-Api POST "/admin/missions/$($mission.id)/mark-reviewed" -Headers $adminHeaders -Body @{
    notes = 'Rota conferida para o smoke test simulado.'
}
Assert-Value 'missão revisada' $mission.status 'READY_FOR_AUTHORIZATION'

$vehicles = Invoke-Api GET '/admin/vehicles' -Headers $adminHeaders
$vehicle = $vehicles | Where-Object { $_.gateway_id -eq 'dev-gateway-01' -and $_.status -eq 'ONLINE' } | Select-Object -First 1
if ($null -eq $vehicle) { throw 'Gateway simulado não publicou um veículo ONLINE.' }
$health = Invoke-Api GET "/admin/vehicles/$($vehicle.id)/health" -Headers $adminHeaders
if (-not ($health.connected -and $health.heartbeat -and $health.preflight_ok)) {
    throw 'Snapshot de saúde não está elegível para autorização.'
}

$authorization = Invoke-Api POST "/admin/missions/$($mission.id)/authorize-flight" -Headers $adminHeaders -Body @{
    vehicle_id = $vehicle.id
    operator_name = 'Operador Smoke'
    controlled_area_confirmed = $true
    checklist = @{
        area_and_conditions_clear = $true
        aircraft_and_payload_inspected = $true
        operator_ready = $true
    }
}
Assert-Value 'missão autorizada' $authorization.mission.status 'AUTHORIZED'

$timeline = [System.Collections.Generic.List[string]]::new()
$deadline = (Get-Date).AddSeconds($TimeoutSeconds)
do {
    $mission = Invoke-Api GET "/admin/missions/$($mission.id)" -Headers $adminHeaders
    if ($timeline.Count -eq 0 -or $timeline[$timeline.Count - 1] -ne [string]$mission.status) {
        $timeline.Add([string]$mission.status)
    }
    if ($mission.status -eq 'COMPLETED') { break }
    Start-Sleep -Seconds 2
} while ((Get-Date) -lt $deadline)

Assert-Value 'fim da missão simulada' $mission.status 'COMPLETED'
$finalOrder = Invoke-Api GET "/admin/orders/$($order.id)" -Headers $adminHeaders
Assert-Value 'fim do pedido simulado' $finalOrder.status 'COMPLETED'

$events = Invoke-Api GET "/admin/events?mission_id=$($mission.id)&limit=100" -Headers $adminHeaders
$telemetry = Invoke-Api GET "/admin/missions/$($mission.id)/telemetry?limit=100" -Headers $adminHeaders
if ($events.Count -lt 1) { throw 'Nenhum evento auditável foi persistido.' }
if ($telemetry.Count -lt 1) { throw 'Nenhuma telemetria simulada foi persistida.' }

[pscustomobject]@{
    mode = 'simulation'
    customer_email = $customerEmail
    order_id = $order.id
    mission_id = $mission.id
    vehicle_id = $vehicle.id
    final_order_status = $finalOrder.status
    final_mission_status = $mission.status
    timeline = @($timeline)
    event_count = $events.Count
    telemetry_count = $telemetry.Count
    physical_delivery_proven = $false
} | ConvertTo-Json -Depth 5
