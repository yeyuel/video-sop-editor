param(
  [string]$DeployRoot = "D:\video-sop-production"
)

$ErrorActionPreference = "Stop"
. (Join-Path $PSScriptRoot "Common.ps1")
Stop-AppTasks -DeployRoot $DeployRoot
Write-Host "Application tasks are stopped."
