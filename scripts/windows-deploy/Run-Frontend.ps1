param(
  [string]$DeployRoot = "D:\video-sop-production"
)

$ErrorActionPreference = "Stop"
. (Join-Path $PSScriptRoot "Common.ps1")
$paths = Get-DeploymentPaths -DeployRoot $DeployRoot
$runtime = Get-DeploymentRuntimeSettings -DeployRoot $paths.Root
$frontendRoot = Join-Path $paths.Current "frontend"
$node = (Get-Command "node.exe" -ErrorAction Stop).Source
$nextCli = Join-Path $frontendRoot "node_modules\next\dist\bin\next"
$stdoutLog = Join-Path $paths.Logs "frontend.stdout.log"
$stderrLog = Join-Path $paths.Logs "frontend.stderr.log"

Set-Location $frontendRoot
$env:NEXT_PUBLIC_API_BASE_URL = "http://127.0.0.1:$($runtime.BackendPort)/api/v1"
$process = Start-Process `
  -FilePath $node `
  -ArgumentList @(
    $nextCli,
    "start",
    "--hostname",
    "0.0.0.0",
    "--port",
    [string]$runtime.FrontendPort
  ) `
  -WorkingDirectory $frontendRoot `
  -RedirectStandardOutput $stdoutLog `
  -RedirectStandardError $stderrLog `
  -WindowStyle Hidden `
  -Wait `
  -PassThru
exit $process.ExitCode
