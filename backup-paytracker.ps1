[CmdletBinding()]
param()

$ErrorActionPreference = "Stop"
$RequiredRoot = "D:\Project\PayTracker"
$ProjectRoot = $PSScriptRoot
if ($ProjectRoot.TrimEnd("\") -ine $RequiredRoot) {
    throw "PayTracker backups must run from $RequiredRoot."
}
Set-Location -LiteralPath $ProjectRoot

$Timestamp = Get-Date -Format "yyyyMMdd-HHmmss"
$BackupRoot = Join-Path $ProjectRoot "backups"
$Destination = Join-Path $BackupRoot "paytracker-backup-$Timestamp"
$ResolvedBackupRoot = [System.IO.Path]::GetFullPath($BackupRoot)
$ResolvedDestination = [System.IO.Path]::GetFullPath($Destination)
if (-not $ResolvedDestination.StartsWith($ResolvedBackupRoot, [System.StringComparison]::OrdinalIgnoreCase)) {
    throw "Refusing to create a backup outside the project backups directory."
}

New-Item -ItemType Directory -LiteralPath $Destination -Force | Out-Null
foreach ($relative in @("data", "uploads", "exports")) {
    $Source = Join-Path $ProjectRoot $relative
    if (Test-Path -LiteralPath $Source) {
        Copy-Item -LiteralPath $Source -Destination $Destination -Recurse
    }
}

$ConfigDestination = Join-Path $Destination "configuration"
New-Item -ItemType Directory -LiteralPath $ConfigDestination -Force | Out-Null
foreach ($relative in @("backend\.env", "backend\.env.example", "backend\alembic.ini")) {
    $Source = Join-Path $ProjectRoot $relative
    if (Test-Path -LiteralPath $Source -PathType Leaf) {
        Copy-Item -LiteralPath $Source -Destination $ConfigDestination
    }
}

$Manifest = @"
PayTracker local backup
Created: $(Get-Date -Format "yyyy-MM-dd HH:mm:ss K")
Source: $ProjectRoot
Contains the SQLite database, uploads, Excel exports and local configuration.
Treat this folder as sensitive financial data.
"@
Set-Content -LiteralPath (Join-Path $Destination "BACKUP-README.txt") -Value $Manifest -Encoding UTF8

Write-Host "Backup created successfully:" -ForegroundColor Green
Write-Host $Destination
Write-Host "No older backups were deleted."
