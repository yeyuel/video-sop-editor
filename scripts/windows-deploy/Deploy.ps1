param(
  [string]$DeployRoot = "D:\video-sop-production",
  [string]$SourceRoot = "",
  [string]$PythonExecutable = "python.exe",
  [switch]$RunTests,
  [switch]$RegisterTasks
)

$ErrorActionPreference = "Stop"
. (Join-Path $PSScriptRoot "Common.ps1")

if (-not $SourceRoot) {
  $SourceRoot = [System.IO.Path]::GetFullPath((Join-Path $PSScriptRoot "..\.."))
}
$SourceRoot = [System.IO.Path]::GetFullPath($SourceRoot)
$paths = Get-DeploymentPaths -DeployRoot $DeployRoot
$runtime = Get-DeploymentRuntimeSettings -DeployRoot $paths.Root

Assert-CommandAvailable -Name $PythonExecutable
Assert-CommandAvailable -Name "npm.cmd"
Assert-CommandAvailable -Name "git.exe"
Assert-CommandAvailable -Name "robocopy.exe"

foreach ($requiredPath in @(
  (Join-Path $paths.Config "backend.env"),
  (Join-Path $paths.Config "frontend.env.local")
)) {
  if (-not (Test-Path -LiteralPath $requiredPath)) {
    throw "Missing deployment config: $requiredPath. Run Initialize-Deployment.ps1 first."
  }
}

$gitSha = (& git.exe -C $SourceRoot rev-parse --short HEAD).Trim()
if ($LASTEXITCODE -ne 0 -or -not $gitSha) {
  throw "Unable to resolve the source Git revision."
}
$releaseId = "{0}-{1}" -f (Get-Date -Format "yyyyMMdd-HHmmss"), $gitSha
$releasePath = Join-Path $paths.Releases $releaseId
New-Item -ItemType Directory -Path $releasePath -Force | Out-Null

Write-Host "Copying source to release: $releaseId"
$excludeDirectories = @(
  (Join-Path $SourceRoot ".git"),
  (Join-Path $SourceRoot "node_modules"),
  (Join-Path $SourceRoot "frontend\node_modules"),
  (Join-Path $SourceRoot "frontend\.next"),
  (Join-Path $SourceRoot "backend\.venv"),
  (Join-Path $SourceRoot "backend\storage"),
  (Join-Path $SourceRoot "backend\.pytest_cache"),
  (Join-Path $SourceRoot ".pytest_cache")
)
$robocopyArgs = @(
  $SourceRoot,
  $releasePath,
  "/E",
  "/NFL",
  "/NDL",
  "/NJH",
  "/NJS",
  "/NP",
  "/R:2",
  "/W:1",
  "/XD"
) + $excludeDirectories + @(
  "/XF",
  ".env",
  ".env.local",
  ".env.production.local",
  "video_sop.db",
  "video_sop.db-shm",
  "video_sop.db-wal"
)
& robocopy.exe @robocopyArgs | Out-Host
if ($LASTEXITCODE -ge 8) {
  throw "Robocopy failed with exit code $LASTEXITCODE."
}

$releaseBackend = Join-Path $releasePath "backend"
$releaseFrontend = Join-Path $releasePath "frontend"
Copy-Item -LiteralPath (Join-Path $paths.Config "backend.env") -Destination (Join-Path $releaseBackend ".env") -Force
Copy-Item -LiteralPath (Join-Path $paths.Config "frontend.env.local") -Destination (Join-Path $releaseFrontend ".env.production.local") -Force

Write-Host "Preparing backend environment."
Invoke-NativeCommand $PythonExecutable "-m" "venv" (Join-Path $releaseBackend ".venv")
$releasePython = Join-Path $releaseBackend ".venv\Scripts\python.exe"
Invoke-NativeCommand $releasePython "-m" "pip" "install" "--disable-pip-version-check" "-r" (Join-Path $releaseBackend "requirements.txt")

Write-Host "Building frontend."
Push-Location $releaseFrontend
try {
  $previousApiBase = $env:NEXT_PUBLIC_API_BASE_URL
  $env:NEXT_PUBLIC_API_BASE_URL = "http://127.0.0.1:$($runtime.BackendPort)/api/v1"
  Invoke-NativeCommand "npm.cmd" "ci"
  if ($RunTests) {
    Invoke-NativeCommand "npm.cmd" "run" "test:unit"
  }
  Invoke-NativeCommand "npm.cmd" "run" "build"
} finally {
  $env:NEXT_PUBLIC_API_BASE_URL = $previousApiBase
  Pop-Location
}

if ($RunTests) {
  Write-Host "Running backend tests."
  Push-Location $releaseBackend
  try {
    Invoke-NativeCommand $releasePython "-m" "pytest" "tests" "-q"
  } finally {
    Pop-Location
  }
}

$previousRelease = Get-JunctionTarget -Path $paths.Current
$backupPath = $null
Stop-AppTasks -DeployRoot $paths.Root

$databasePath = Join-Path $paths.Data "video_sop.db"
if (Test-Path -LiteralPath $databasePath) {
  $backupPath = Join-Path $paths.Backups ("video_sop-{0}-before-{1}.db" -f (Get-Date -Format "yyyyMMdd-HHmmss"), $gitSha)
  Invoke-NativeCommand $releasePython (Join-Path $releasePath "scripts\windows-deploy\backup_sqlite.py") "backup" $databasePath $backupPath
  Write-Host "Database backup created: $backupPath"
}

try {
  if ($previousRelease) {
    Set-Content -LiteralPath (Join-Path $paths.State "previous-release.txt") -Value $previousRelease -Encoding ascii
  }
  if ($backupPath) {
    Set-Content -LiteralPath (Join-Path $paths.State "last-database-backup.txt") -Value $backupPath -Encoding ascii
  }

  Set-CurrentRelease -CurrentPath $paths.Current -ReleasePath $releasePath -ReleasesRoot $paths.Releases

  $taskNames = Get-AppTaskNames
  $tasksMissing = -not (Get-ScheduledTask -TaskName $taskNames.Backend -ErrorAction SilentlyContinue) -or -not (Get-ScheduledTask -TaskName $taskNames.Frontend -ErrorAction SilentlyContinue)
  if ($RegisterTasks -or $tasksMissing) {
    & (Join-Path $releasePath "scripts\windows-deploy\Register-AppTasks.ps1") -DeployRoot $paths.Root
  }
  & (Join-Path $releasePath "scripts\windows-deploy\Start-App.ps1") -DeployRoot $paths.Root
  Set-Content -LiteralPath (Join-Path $paths.State "current-release.txt") -Value $releasePath -Encoding ascii
  Write-Host "Deployment completed: $releaseId"
} catch {
  $deploymentError = $_
  Stop-AppTasks -DeployRoot $paths.Root
  if ($previousRelease) {
    Write-Warning "Deployment failed. Restoring previous release: $previousRelease"
    Set-CurrentRelease -CurrentPath $paths.Current -ReleasePath $previousRelease -ReleasesRoot $paths.Releases
    if ($backupPath) {
      Invoke-NativeCommand $releasePython (Join-Path $releasePath "scripts\windows-deploy\backup_sqlite.py") "restore" $backupPath $databasePath
    }
    & (Join-Path $previousRelease "scripts\windows-deploy\Register-AppTasks.ps1") -DeployRoot $paths.Root
    & (Join-Path $previousRelease "scripts\windows-deploy\Start-App.ps1") -DeployRoot $paths.Root
  } elseif (Test-Path -LiteralPath $paths.Current) {
    Remove-DirectoryJunction -Path $paths.Current
  }
  throw $deploymentError
}
