param(
  [string]$DeployRoot = "D:\video-sop-production"
)

$ErrorActionPreference = "Stop"
. (Join-Path $PSScriptRoot "Common.ps1")

$paths = Get-DeploymentPaths -DeployRoot $DeployRoot
$runtime = Get-DeploymentRuntimeSettings -DeployRoot $paths.Root
$taskNames = Get-AppTaskNames
$currentTarget = Get-JunctionTarget -Path $paths.Current
Write-Host "Current release: $currentTarget"

foreach ($taskName in @($taskNames.Backend, $taskNames.Frontend)) {
  $task = Get-ScheduledTask -TaskName $taskName -ErrorAction SilentlyContinue
  if ($task) {
    $info = Get-ScheduledTaskInfo -TaskName $taskName
    Write-Host "$taskName state=$($task.State) lastResult=$($info.LastTaskResult)"
  } else {
    Write-Host "$taskName is not registered."
  }
}

foreach ($endpoint in @("http://127.0.0.1:$($runtime.BackendPort)/api/v1/health", "http://127.0.0.1:$($runtime.FrontendPort)/login")) {
  try {
    $response = Invoke-WebRequest -Uri $endpoint -UseBasicParsing -TimeoutSec 5
    Write-Host "$endpoint -> $($response.StatusCode)"
  } catch {
    Write-Host "$endpoint -> unavailable"
  }
}
