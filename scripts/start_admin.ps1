[CmdletBinding()]
param()

$ErrorActionPreference = 'Stop'
$projectRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
Push-Location (Join-Path $projectRoot 'admin_web')
try {
    & npm.cmd run dev -- --host 0.0.0.0
    if ($LASTEXITCODE -ne 0) { throw "Painel encerrou com exit code $LASTEXITCODE." }
}
finally { Pop-Location }
