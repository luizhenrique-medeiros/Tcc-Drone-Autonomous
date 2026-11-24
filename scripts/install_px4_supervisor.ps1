[CmdletBinding()]
param()

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
$supervisor = Join-Path $PSScriptRoot 'supervise_px4_connection.ps1'
& $supervisor -ValidateOnly
$taskName = 'DevCore PX4 Observacao'
if (Get-ScheduledTask -TaskName $taskName -ErrorAction SilentlyContinue) {
    throw "A tarefa '$taskName' ja existe. Inspecione-a antes de substitui-la."
}
$action = New-ScheduledTaskAction -Execute (Join-Path $PSHOME 'powershell.exe') `
    -Argument "-NoProfile -NonInteractive -ExecutionPolicy Bypass -File `"$supervisor`""
$trigger = New-ScheduledTaskTrigger -AtLogOn -User "$env:USERDOMAIN\$env:USERNAME"
$settings = New-ScheduledTaskSettingsSet -MultipleInstances IgnoreNew -ExecutionTimeLimit ([TimeSpan]::Zero) `
    -RestartCount 3 -RestartInterval (New-TimeSpan -Minutes 1) -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries
Register-ScheduledTask -TaskName $taskName -Action $action -Trigger $trigger -Settings $settings `
    -Description 'Supervisao passiva do roteador COM7 e gateway PX4 local; nao autoriza comandos.' | Out-Null
Start-ScheduledTask -TaskName $taskName
Write-Output "Tarefa '$taskName' registrada para o login deste usuario e iniciada."
