[CmdletBinding()]
param(
    [switch]$Lan
)

$ErrorActionPreference = "Stop"
$RequiredRoot = "D:\Project\PayTracker"
$ProjectRoot = $PSScriptRoot
if ($ProjectRoot.TrimEnd("\") -ine $RequiredRoot) {
    throw "PayTracker must run from $RequiredRoot. Current script location: $ProjectRoot"
}
Set-Location -LiteralPath $ProjectRoot

$Python = Join-Path $ProjectRoot ".venv\Scripts\python.exe"
if (-not (Test-Path -LiteralPath $Python)) {
    throw "PayTracker is not set up. Run .\setup-paytracker.ps1 first."
}

$FrontendRoot = Join-Path $ProjectRoot "frontend"
$FrontendIndex = Join-Path $FrontendRoot "dist\index.html"
$FrontendInputs = @(
    (Join-Path $FrontendRoot "src"),
    (Join-Path $FrontendRoot "package.json"),
    (Join-Path $FrontendRoot "vite.config.ts"),
    (Join-Path $FrontendRoot "tailwind.config.js")
) | Where-Object { Test-Path -LiteralPath $_ }
$LatestFrontendInput = $FrontendInputs |
    ForEach-Object {
        if ((Get-Item -LiteralPath $_).PSIsContainer) {
            Get-ChildItem -LiteralPath $_ -Recurse -File
        } else {
            Get-Item -LiteralPath $_
        }
    } |
    Sort-Object -Property LastWriteTime -Descending |
    Select-Object -First 1
$FrontendNeedsBuild = -not (Test-Path -LiteralPath $FrontendIndex)
if (-not $FrontendNeedsBuild -and $LatestFrontendInput) {
    $FrontendNeedsBuild = $LatestFrontendInput.LastWriteTime -gt (Get-Item -LiteralPath $FrontendIndex).LastWriteTime
}
if ($FrontendNeedsBuild) {
    if (-not (Get-Command npm -ErrorAction SilentlyContinue)) {
        throw "The frontend needs rebuilding, but npm was not found. Install Node.js or run .\setup-paytracker.ps1."
    }
    Write-Host "Frontend changes detected. Building the latest interface..." -ForegroundColor Cyan
    Push-Location $FrontendRoot
    try {
        & npm run build
        if ($LASTEXITCODE -ne 0) {
            throw "Frontend build failed. Review the npm errors above."
        }
    } finally {
        Pop-Location
    }
}

Write-Host "Checking local database migrations..." -ForegroundColor Cyan
Push-Location (Join-Path $ProjectRoot "backend")
try {
    & $Python -m alembic upgrade head
    if ($LASTEXITCODE -ne 0) {
        throw "Database migration failed. Review the Alembic errors above."
    }
} finally {
    Pop-Location
}

$HostAddress = if ($Lan) { "0.0.0.0" } else { "127.0.0.1" }
$Url = "http://127.0.0.1:8000"

Write-Host "PayTracker is local-first. Uploaded financial documents stay on this computer." -ForegroundColor Cyan
if ($Lan) {
    $PrivateAddress = Get-NetIPAddress -AddressFamily IPv4 -ErrorAction SilentlyContinue |
        Where-Object {
            $_.IPAddress -like "10.*" -or
            $_.IPAddress -like "192.168.*" -or
            $_.IPAddress -match "^172\.(1[6-9]|2[0-9]|3[01])\."
        } |
        Where-Object {
            $_.PrefixOrigin -ne "WellKnown"
        } |
        Sort-Object -Property InterfaceMetric |
        Select-Object -First 1 -ExpandProperty IPAddress
    if (-not $PrivateAddress) {
        Write-Warning "A private IPv4 address could not be detected. Check your Wi-Fi connection."
        $PhoneUrl = "http://<laptop-private-ip>:8000"
    } else {
        $PhoneUrl = "http://${PrivateAddress}:8000"
    }
    Write-Host ""
    Write-Host "LAN MODE - use only on trusted private Wi-Fi" -ForegroundColor Yellow
    Write-Host "Phone URL: $PhoneUrl" -ForegroundColor Green
    Write-Host "Windows Firewall may ask you to allow access. Select Private networks only."
    Write-Host "The laptop must remain on and this window must remain open."
    Write-Host "PayTracker does not expose itself to the public internet."
} else {
    Write-Host "Laptop URL: $Url" -ForegroundColor Green
}

Write-Host "API documentation: http://127.0.0.1:8000/api/docs"
Write-Host "Press Ctrl+C to stop PayTracker."
Push-Location (Join-Path $ProjectRoot "backend")
try {
    & $Python -m uvicorn app.main:app --host $HostAddress --port 8000
} finally {
    Pop-Location
}
