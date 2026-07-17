$ErrorActionPreference = "Stop"

function Get-DeploymentPaths {
  param([Parameter(Mandatory = $true)][string]$DeployRoot)

  $root = [System.IO.Path]::GetFullPath($DeployRoot)
  return @{
    Root = $root
    Releases = Join-Path $root "releases"
    Current = Join-Path $root "current"
    Config = Join-Path $root "config"
    Data = Join-Path $root "data"
    Backups = Join-Path $root "data\backups"
    Storage = Join-Path $root "data\storage"
    Logs = Join-Path $root "logs"
    State = Join-Path $root "state"
  }
}

function Get-AppTaskNames {
  return @{
    Backend = "VideoSopEditor-Backend"
    Frontend = "VideoSopEditor-Frontend"
  }
}

function Get-DeploymentRuntimeSettings {
  param([Parameter(Mandatory = $true)][string]$DeployRoot)

  $paths = Get-DeploymentPaths -DeployRoot $DeployRoot
  $values = @{
    BACKEND_PORT = "8100"
    FRONTEND_PORT = "3100"
  }
  $settingsPath = Join-Path $paths.Config "deployment.env"
  if (Test-Path -LiteralPath $settingsPath) {
    foreach ($line in Get-Content -LiteralPath $settingsPath) {
      $trimmed = $line.Trim()
      if (-not $trimmed -or $trimmed.StartsWith("#") -or -not $trimmed.Contains("=")) {
        continue
      }
      $parts = $trimmed.Split("=", 2)
      $key = $parts[0].Trim()
      if ($values.ContainsKey($key)) {
        $values[$key] = $parts[1].Trim()
      }
    }
  }

  try {
    $backendPort = [int]$values.BACKEND_PORT
    $frontendPort = [int]$values.FRONTEND_PORT
  } catch {
    throw "Deployment ports must be integers in: $settingsPath"
  }
  foreach ($port in @($backendPort, $frontendPort)) {
    if ($port -lt 1 -or $port -gt 65535) {
      throw "Deployment port is outside the valid range: $port"
    }
  }
  if ($backendPort -eq $frontendPort) {
    throw "Backend and frontend deployment ports must be different."
  }

  return @{
    BackendPort = $backendPort
    FrontendPort = $frontendPort
  }
}

function Assert-CommandAvailable {
  param([Parameter(Mandatory = $true)][string]$Name)

  if (-not (Get-Command $Name -ErrorAction SilentlyContinue)) {
    throw "Required command is not available: $Name"
  }
}

function Invoke-NativeCommand {
  param(
    [Parameter(Mandatory = $true)][string]$FilePath,
    [Parameter(ValueFromRemainingArguments = $true)][string[]]$Arguments
  )

  & $FilePath @Arguments
  if ($LASTEXITCODE -ne 0) {
    throw "Command failed with exit code ${LASTEXITCODE}: $FilePath $($Arguments -join ' ')"
  }
}

function Get-JunctionTarget {
  param([Parameter(Mandatory = $true)][string]$Path)

  if (-not (Test-Path -LiteralPath $Path)) {
    return $null
  }

  $item = Get-Item -LiteralPath $Path -Force
  if (($item.Attributes -band [System.IO.FileAttributes]::ReparsePoint) -eq 0) {
    throw "Expected a junction but found a regular path: $Path"
  }

  $target = $item.Target
  if ($target -is [array]) {
    return [string]$target[0]
  }
  return [string]$target
}

function Remove-DirectoryJunction {
  param([Parameter(Mandatory = $true)][string]$Path)

  if (-not (Test-Path -LiteralPath $Path)) {
    return
  }
  [void](Get-JunctionTarget -Path $Path)
  [System.IO.Directory]::Delete($Path)
}

function Set-CurrentRelease {
  param(
    [Parameter(Mandatory = $true)][string]$CurrentPath,
    [Parameter(Mandatory = $true)][string]$ReleasePath,
    [Parameter(Mandatory = $true)][string]$ReleasesRoot
  )

  $resolvedRelease = [System.IO.Path]::GetFullPath($ReleasePath)
  $resolvedReleasesRoot = [System.IO.Path]::GetFullPath($ReleasesRoot).TrimEnd('\') + '\'
  if (-not $resolvedRelease.StartsWith($resolvedReleasesRoot, [System.StringComparison]::OrdinalIgnoreCase)) {
    throw "Release path must stay inside the releases directory: $resolvedRelease"
  }
  if (-not (Test-Path -LiteralPath $resolvedRelease -PathType Container)) {
    throw "Release directory does not exist: $resolvedRelease"
  }

  if (Test-Path -LiteralPath $CurrentPath) {
    Remove-DirectoryJunction -Path $CurrentPath
  }
  New-Item -ItemType Junction -Path $CurrentPath -Target $resolvedRelease | Out-Null
}

function Wait-HttpEndpoint {
  param(
    [Parameter(Mandatory = $true)][string]$Uri,
    [int]$TimeoutSec = 60
  )

  $deadline = (Get-Date).AddSeconds($TimeoutSec)
  do {
    try {
      $response = Invoke-WebRequest -Uri $Uri -UseBasicParsing -TimeoutSec 5
      if ($response.StatusCode -ge 200 -and $response.StatusCode -lt 400) {
        return
      }
    } catch {
      Start-Sleep -Seconds 2
    }
  } while ((Get-Date) -lt $deadline)

  throw "Health check timed out: $Uri"
}

function Stop-DeploymentProcessTree {
  param(
    [Parameter(Mandatory = $true)][int]$ProcessId,
    [Parameter(Mandatory = $true)][string]$DeployRoot
  )

  $root = [System.IO.Path]::GetFullPath($DeployRoot)
  $processIds = New-Object System.Collections.Generic.List[int]
  $ownedProcessIds = @()
  $currentProcessId = $ProcessId

  for ($depth = 0; $depth -lt 6 -and $currentProcessId -gt 0; $depth++) {
    $process = Get-CimInstance Win32_Process -Filter "ProcessId = $currentProcessId" -ErrorAction SilentlyContinue
    if (-not $process) {
      break
    }
    $processIds.Add([int]$process.ProcessId)
    $identity = "{0}`n{1}" -f ([string]$process.ExecutablePath), ([string]$process.CommandLine)
    if ($identity.IndexOf($root, [System.StringComparison]::OrdinalIgnoreCase) -ge 0) {
      $ownedProcessIds = @($processIds)
    }
    $currentProcessId = [int]$process.ParentProcessId
  }

  if ($ownedProcessIds.Count -eq 0) {
    return $false
  }
  foreach ($ownedProcessId in $ownedProcessIds) {
    Stop-Process -Id $ownedProcessId -Force -ErrorAction SilentlyContinue
  }
  return $true
}

function Stop-AppTasks {
  param([Parameter(Mandatory = $true)][string]$DeployRoot)

  $paths = Get-DeploymentPaths -DeployRoot $DeployRoot
  $runtime = Get-DeploymentRuntimeSettings -DeployRoot $paths.Root
  $tasks = Get-AppTaskNames
  foreach ($taskName in @($tasks.Frontend, $tasks.Backend)) {
    $task = Get-ScheduledTask -TaskName $taskName -ErrorAction SilentlyContinue
    if ($task -and $task.State -ne "Ready") {
      Stop-ScheduledTask -TaskName $taskName -ErrorAction SilentlyContinue
    }
  }
  Start-Sleep -Seconds 2

  foreach ($port in @($runtime.BackendPort, $runtime.FrontendPort)) {
    $listeners = Get-NetTCPConnection -State Listen -LocalPort $port -ErrorAction SilentlyContinue
    foreach ($listener in $listeners) {
      $stopped = Stop-DeploymentProcessTree -ProcessId $listener.OwningProcess -DeployRoot $paths.Root
      if (-not $stopped) {
        throw "Port $port is occupied by a process outside the deployment root."
      }
    }
  }
}
