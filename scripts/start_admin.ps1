[CmdletBinding()]
param(
    [string]$HostAddress = '127.0.0.1',
    [int]$Port = 5173
)

$ErrorActionPreference = 'Stop'
$projectRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$envFile = Join-Path $projectRoot '.env'

function Import-ProjectEnvValue {
    param([Parameter(Mandatory = $true)][string]$Name)

    if (-not [string]::IsNullOrWhiteSpace((Get-Item -Path "Env:$Name" -ErrorAction SilentlyContinue).Value)) {
        return
    }
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

@(
    'VITE_API_BASE_URL',
    'VITE_WS_BASE_URL',
    'VITE_DEMO_MODE',
    'MAPTILER_WEB_API_KEY',
    'MAPTILER_STYLE_URL'
) | ForEach-Object { Import-ProjectEnvValue -Name $_ }

if ([string]::IsNullOrWhiteSpace($env:MAPTILER_WEB_API_KEY)) {
    Write-Warning 'MAPTILER_WEB_API_KEY não encontrada; o painel exibirá o fallback coordenado identificado.'
}

Push-Location (Join-Path $projectRoot 'admin_web')
try {
    Write-Host "Painel administrativo: http://localhost:$Port"
    & npm.cmd run dev -- --host $HostAddress --port $Port --strictPort
    if ($LASTEXITCODE -ne 0) { throw "Painel encerrou com exit code $LASTEXITCODE." }
}
finally { Pop-Location }
