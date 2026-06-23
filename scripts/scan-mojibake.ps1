$ErrorActionPreference = "Stop"

$suspiciousFragments = @(
  "寤鸿",
  "鏂囨",
  "鐢熸垚",
  "澶辫触",
  "璇峰厛",
  "闊抽",
  "鏆楀満",
  "涓婁紶",
  "鏈笂浼",
  "瑙勫垯",
  "鑷姩",
  "寮鸿妭",
  "绋宠妭",
  "鑸掑睍",
  "銆?",
  "锟"
)

$replacementChar = [char]0xfffd
$textExtensions = @(
  ".ts", ".tsx", ".js", ".jsx", ".py", ".md", ".json", ".css",
  ".yml", ".yaml", ".txt", ".env", ".example"
)

function Test-TextFile([string]$path) {
  $name = [System.IO.Path]::GetFileName($path)
  if ($name -like ".env*") {
    return $true
  }

  $extension = [System.IO.Path]::GetExtension($path).ToLowerInvariant()
  return $textExtensions -contains $extension
}

$trackedFiles = git ls-files frontend backend docs .editorconfig .vscode 2>$null
if (-not $trackedFiles) {
  Write-Host "未读取到任何受 Git 管理的文件。" -ForegroundColor Yellow
  exit 0
}

$hits = New-Object System.Collections.Generic.List[object]

foreach ($relativePath in $trackedFiles) {
  if (-not (Test-TextFile $relativePath)) {
    continue
  }

  $absolutePath = Join-Path (Get-Location) $relativePath
  if (-not (Test-Path -LiteralPath $absolutePath)) {
    continue
  }

  try {
    $content = Get-Content -LiteralPath $absolutePath -Encoding utf8 -Raw
  } catch {
    continue
  }

  $matched = New-Object System.Collections.Generic.List[string]
  foreach ($fragment in $suspiciousFragments) {
    if ($content.Contains($fragment)) {
      $matched.Add($fragment)
    }
  }

  if ($content.Contains($replacementChar)) {
    $matched.Add("U+FFFD")
  }

  if ($matched.Count -gt 0) {
    $hits.Add(
      [PSCustomObject]@{
        File     = $relativePath
        Patterns = ($matched -join ", ")
      }
    )
  }
}

if ($hits.Count -eq 0) {
  Write-Host "未发现可疑乱码片段。" -ForegroundColor Green
  exit 0
}

$hits | Sort-Object File | Format-Table -AutoSize
Write-Host ""
Write-Host ("TOTAL_FILES={0}" -f $hits.Count) -ForegroundColor Yellow
