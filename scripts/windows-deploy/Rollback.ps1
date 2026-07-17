param(
  [string]$DeployRoot = "D:\video-sop-production",
  [string]$RestoreDatabaseFrom = ""
)

$ErrorActionPreference = "Stop"
. (Join-Path $PSScriptRoot "Common.ps1")

$paths = Get-DeploymentPaths -DeployRoot $DeployRoot
$previousState = Join-Path $paths.State "previous-release.txt"
if (-not (Test-Path -LiteralPath $previousState)) {
  throw "No previous release is recorded."
}

$previousRelease = (Get-Content -LiteralPath $previousState -Raw).Trim()
$currentRelease = Get-JunctionTarget -Path $paths.Current
if (-not $currentRelease) {
  throw "No current release is active."
}

Stop-AppTasks -DeployRoot $paths.Root
$databasePath = Join-Path $paths.Data "video_sop.db"
$currentPython = Join-Path $currentRelease "backend\.venv\Scripts\python.exe"
$safetyBackup = $null
if (Test-Path -LiteralPath $databasePath) {
  $safetyBackup = Join-Path $paths.Backups ("video_sop-{0}-before-manual-rollback.db" -f (Get-Date -Format "yyyyMMdd-HHmmss"))
  Invoke-NativeCommand $currentPython (Join-Path $currentRelease "scripts\windows-deploy\backup_sqlite.py") "backup" $databasePath $safetyBackup
  Write-Host "Safety backup created: $safetyBackup"
}

Set-CurrentRelease -CurrentPath $paths.Current -ReleasePath $previousRelease -ReleasesRoot $paths.Releases
if ($RestoreDatabaseFrom) {
  $backup = [System.IO.Path]::GetFullPath($RestoreDatabaseFrom)
  Invoke-NativeCommand $currentPython (Join-Path $currentRelease "scripts\windows-deploy\backup_sqlite.py") "restore" $backup $databasePath
  Write-Host "Database restored from: $backup"
}

Set-Content -LiteralPath $previousState -Value $currentRelease -Encoding ascii
& (Join-Path $previousRelease "scripts\windows-deploy\Register-AppTasks.ps1") -DeployRoot $paths.Root
& (Join-Path $previousRelease "scripts\windows-deploy\Start-App.ps1") -DeployRoot $paths.Root
Write-Host "Rollback completed: $previousRelease"
