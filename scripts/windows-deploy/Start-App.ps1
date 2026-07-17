param(
  [string]$DeployRoot = "D:\video-sop-production",
  [int]$TimeoutSec = 90
)

$ErrorActionPreference = "Stop"
. (Join-Path $PSScriptRoot "Common.ps1")

$taskNames = Get-AppTaskNames
$runtime = Get-DeploymentRuntimeSettings -DeployRoot $DeployRoot
foreach ($taskName in @($taskNames.Backend, $taskNames.Frontend)) {
  if (-not (Get-ScheduledTask -TaskName $taskName -ErrorAction SilentlyContinue)) {
    throw "Scheduled task is not registered: $taskName"
  }
  Start-ScheduledTask -TaskName $taskName
}

Wait-HttpEndpoint -Uri "http://127.0.0.1:$($runtime.BackendPort)/api/v1/health" -TimeoutSec $TimeoutSec
Wait-HttpEndpoint -Uri "http://127.0.0.1:$($runtime.FrontendPort)/login" -TimeoutSec $TimeoutSec
$notRunning = @($taskNames.Backend, $taskNames.Frontend) | Where-Object {
  (Get-ScheduledTask -TaskName $_).State -ne "Running"
}
if ($notRunning.Count -gt 0) {
  throw "Application process is not tracked by its scheduled task: $($notRunning -join ', ')"
}
Write-Host "Application is healthy: http://127.0.0.1:$($runtime.FrontendPort)"
