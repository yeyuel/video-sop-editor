param(
  [string]$DeployRoot = "D:\video-sop-production"
)

$ErrorActionPreference = "Stop"
. (Join-Path $PSScriptRoot "Common.ps1")
$paths = Get-DeploymentPaths -DeployRoot $DeployRoot
$runtime = Get-DeploymentRuntimeSettings -DeployRoot $paths.Root
$backendRoot = Join-Path $paths.Current "backend"
$python = Join-Path $backendRoot ".venv\Scripts\python.exe"
$stdoutLog = Join-Path $paths.Logs "backend.stdout.log"
$stderrLog = Join-Path $paths.Logs "backend.stderr.log"

Set-Location $backendRoot
$env:APP_PORT = [string]$runtime.BackendPort
$env:LLM_OAUTH_REDIRECT_URI = "http://127.0.0.1:$($runtime.FrontendPort)/settings/llm/oauth/callback"
$process = Start-Process `
  -FilePath $python `
  -ArgumentList @(
    "-m",
    "uvicorn",
    "app.main:app",
    "--host",
    "127.0.0.1",
    "--port",
    [string]$runtime.BackendPort,
    "--workers",
    "1",
    "--timeout-graceful-shutdown",
    "10"
  ) `
  -WorkingDirectory $backendRoot `
  -RedirectStandardOutput $stdoutLog `
  -RedirectStandardError $stderrLog `
  -WindowStyle Hidden `
  -Wait `
  -PassThru
exit $process.ExitCode
