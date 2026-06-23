$ErrorActionPreference = "Stop"

git config core.hooksPath .githooks

Write-Host "Git hooks path has been set to .githooks" -ForegroundColor Green
Write-Host "Pre-commit will now run scripts/scan-mojibake.ps1 before each commit." -ForegroundColor Green
