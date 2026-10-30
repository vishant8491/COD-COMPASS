# PowerShell submission packager for COD Compass
# Packages clean submission archive inside project workspace avoiding sandbox boundary violations

$projectPath = (Get-Location).Path
$zipPath = Join-Path $projectPath "COD_Compass_Submission.zip"
$stagePath = Join-Path $env:TEMP ("CODCompassZip_" + [guid]::NewGuid().ToString("N"))

if (Test-Path $zipPath) {
    Remove-Item -Path $zipPath -Force
}

New-Item -ItemType Directory -Path $stagePath | Out-Null

robocopy $projectPath $stagePath /E /R:1 /W:1 /NFL /NDL /NJH /NJS /NP `
  /XD node_modules .venv venv .git __pycache__ .pytest_cache .mypy_cache .ruff_cache .idea .vscode dist build coverage htmlcov `
  /XF ".env" ".env.*" "*.db" "*.db-*" "*.sqlite" "*.sqlite-*" "*.sqlite3" "*.sqlite3-*" "*.pyc" "*.pyo" "*.zip" "*.log" ".coverage" "orders_sample.csv"

if ($LASTEXITCODE -ge 8) {
    throw "Robocopy encountered an error copying files."
}

# Ensure safe environment template is included
if (Test-Path "$projectPath\.env.example") {
    Copy-Item "$projectPath\.env.example" "$stagePath\.env.example" -Force
}

Add-Type -AssemblyName System.IO.Compression.FileSystem
[System.IO.Compression.ZipFile]::CreateFromDirectory($stagePath, $zipPath)

Remove-Item -LiteralPath $stagePath -Recurse -Force

Write-Host "Clean submission ZIP created successfully at: $zipPath" -ForegroundColor Green

