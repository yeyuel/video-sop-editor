param(
  [string]$DeployRoot = "D:\video-sop-production"
)

$ErrorActionPreference = "Stop"
. (Join-Path $PSScriptRoot "Common.ps1")

$paths = Get-DeploymentPaths -DeployRoot $DeployRoot
if (-not (Test-Path -LiteralPath $paths.Current)) {
  throw "Deploy an application release before registering tasks."
}

$taskNames = Get-AppTaskNames
$powerShell = "$env:SystemRoot\System32\WindowsPowerShell\v1.0\powershell.exe"
$principalName = if ($env:USERDOMAIN) { "$env:USERDOMAIN\$env:USERNAME" } else { $env:USERNAME }
$principal = New-ScheduledTaskPrincipal -UserId $principalName -LogonType Interactive -RunLevel Limited
$trigger = New-ScheduledTaskTrigger -AtLogOn -User $principalName
$settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -RestartCount 3 -RestartInterval (New-TimeSpan -Minutes 1) -ExecutionTimeLimit ([TimeSpan]::Zero) -Hidden

$definitions = @(
  @{
    Name = $taskNames.Backend
    Script = Join-Path $paths.Current "scripts\windows-deploy\Run-Backend.ps1"
  },
  @{
    Name = $taskNames.Frontend
    Script = Join-Path $paths.Current "scripts\windows-deploy\Run-Frontend.ps1"
  }
)

foreach ($definition in $definitions) {
  $arguments = "-NoProfile -NonInteractive -WindowStyle Hidden -ExecutionPolicy Bypass -File `"$($definition.Script)`" -DeployRoot `"$($paths.Root)`""
  $action = New-ScheduledTaskAction -Execute $powerShell -Argument $arguments
  Register-ScheduledTask -TaskName $definition.Name -Action $action -Trigger $trigger -Principal $principal -Settings $settings -Force | Out-Null
  Write-Host "Registered task: $($definition.Name)"
}
