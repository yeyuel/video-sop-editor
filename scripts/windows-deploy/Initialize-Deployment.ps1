param(
  [string]$DeployRoot = "D:\video-sop-production"
)

$ErrorActionPreference = "Stop"
. (Join-Path $PSScriptRoot "Common.ps1")

$paths = Get-DeploymentPaths -DeployRoot $DeployRoot
foreach ($path in @(
  $paths.Root,
  $paths.Releases,
  $paths.Config,
  $paths.Data,
  $paths.Backups,
  $paths.Storage,
  $paths.Logs,
  $paths.State
)) {
  New-Item -ItemType Directory -Path $path -Force | Out-Null
}

$backendEnv = Join-Path $paths.Config "backend.env"
$runtimeEnv = Join-Path $paths.Config "deployment.env"
if (-not (Test-Path -LiteralPath $runtimeEnv)) {
  @"
BACKEND_PORT=8100
FRONTEND_PORT=3100
"@ | Set-Content -LiteralPath $runtimeEnv -Encoding ascii
  Write-Host "Created: $runtimeEnv"
}

$runtime = Get-DeploymentRuntimeSettings -DeployRoot $paths.Root
if (-not (Test-Path -LiteralPath $backendEnv)) {
  $secretBytes = New-Object byte[] 48
  [System.Security.Cryptography.RandomNumberGenerator]::Create().GetBytes($secretBytes)
  $secret = [Convert]::ToBase64String($secretBytes)
  $databasePath = (Join-Path $paths.Data "video_sop.db").Replace('\', '/')
  $storagePath = $paths.Storage.Replace('\', '/')
  @"
APP_ENV=production
APP_NAME=video-sop-editor-api
APP_HOST=127.0.0.1
APP_PORT=$($runtime.BackendPort)
APP_GRACEFUL_SHUTDOWN_SEC=10
DATABASE_URL=sqlite:///$databasePath
SQLITE_BUSY_TIMEOUT_MS=5000
STORAGE_DIR=$storagePath
APP_SECRET_KEY=$secret
LLM_OAUTH_REDIRECT_URI=http://127.0.0.1:$($runtime.FrontendPort)/settings/llm/oauth/callback
LLM_OAUTH_MOCK=false
VISION_USE_MOCK=false
"@ | Set-Content -LiteralPath $backendEnv -Encoding ascii
  Write-Host "Created: $backendEnv"
}

$frontendEnv = Join-Path $paths.Config "frontend.env.local"
if (-not (Test-Path -LiteralPath $frontendEnv)) {
  @"
NEXT_PUBLIC_API_BASE_URL=http://127.0.0.1:$($runtime.BackendPort)/api/v1
"@ | Set-Content -LiteralPath $frontendEnv -Encoding ascii
  Write-Host "Created: $frontendEnv"
}

Write-Host "Deployment directories are ready: $($paths.Root)"
Write-Host "Review config files before the first deployment."
Write-Host "Next command:"
Write-Host ".\scripts\windows-deploy\Deploy.ps1 -DeployRoot `"$($paths.Root)`" -RegisterTasks -RunTests"
