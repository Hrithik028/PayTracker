[CmdletBinding()]
param()

$ErrorActionPreference = "Stop"
$RequiredRoot = "D:\Project\PayTracker"
$ProjectRoot = $PSScriptRoot

if ($ProjectRoot.TrimEnd("\") -ine $RequiredRoot) {
    throw "PayTracker must be located at $RequiredRoot. Current script location: $ProjectRoot"
}

Set-Location -LiteralPath $ProjectRoot
Write-Host "Setting up PayTracker at $ProjectRoot" -ForegroundColor Cyan

function Get-Python312 {
    $candidates = @()
    if (Get-Command py -ErrorAction SilentlyContinue) {
        $candidates += [pscustomobject]@{
            Executable = "py"
            Arguments = @("-3.12")
        }
    }
    if (Get-Command python -ErrorAction SilentlyContinue) {
        $candidates += [pscustomobject]@{
            Executable = "python"
            Arguments = @()
        }
    }
    foreach ($candidate in $candidates) {
        try {
            $version = & $candidate.Executable @($candidate.Arguments) --version 2>&1
            if ($version -match "Python 3\.12") {
                return $candidate
            }
        } catch {
            continue
        }
    }
    return $null
}

$PythonCommand = Get-Python312
if (-not $PythonCommand) {
    throw @"
Python 3.12 was not found.
Install Python 3.12 for Windows from https://www.python.org/downloads/windows/
Enable 'Add python.exe to PATH', then rerun:
  .\setup-paytracker.ps1
"@
}

if (-not (Get-Command node -ErrorAction SilentlyContinue)) {
    throw "Node.js was not found. Install Node.js 20 LTS or later, then rerun setup."
}
$NodeMajor = [int]((& node --version).TrimStart("v").Split(".")[0])
if ($NodeMajor -lt 20) {
    throw "Node.js 20 or later is required. Detected: $(& node --version)"
}
if (-not (Get-Command npm -ErrorAction SilentlyContinue) -and -not (Get-Command npm.cmd -ErrorAction SilentlyContinue)) {
    throw "npm was not found. Reinstall Node.js with npm included."
}

foreach ($relative in @(
    "data",
    "uploads\payslips",
    "uploads\timing-screenshots",
    "exports",
    "backups",
    "samples"
)) {
    New-Item -ItemType Directory -Path (Join-Path $ProjectRoot $relative) -Force | Out-Null
}

$VenvPython = Join-Path $ProjectRoot ".venv\Scripts\python.exe"
if (-not (Test-Path -LiteralPath $VenvPython)) {
    Write-Host "Creating project virtual environment..." -ForegroundColor Cyan
    & $PythonCommand.Executable @($PythonCommand.Arguments) -m venv (Join-Path $ProjectRoot ".venv")
}

Write-Host "Installing backend dependencies inside .venv..." -ForegroundColor Cyan
& $VenvPython -m pip install --upgrade pip
& $VenvPython -m pip install -r (Join-Path $ProjectRoot "backend\requirements.txt")

$BackendEnv = Join-Path $ProjectRoot "backend\.env"
if (-not (Test-Path -LiteralPath $BackendEnv)) {
    Copy-Item -LiteralPath (Join-Path $ProjectRoot "backend\.env.example") -Destination $BackendEnv
}

Write-Host "Installing and building frontend..." -ForegroundColor Cyan
Push-Location (Join-Path $ProjectRoot "frontend")
try {
    if (Test-Path -LiteralPath "package-lock.json") {
        & npm.cmd ci
    } else {
        & npm.cmd install
    }
    & npm.cmd run build
} finally {
    Pop-Location
}

Write-Host "Running database migrations..." -ForegroundColor Cyan
Push-Location (Join-Path $ProjectRoot "backend")
try {
    & $VenvPython -m alembic upgrade head
} finally {
    Pop-Location
}

Write-Host "Creating fictional sample documents..." -ForegroundColor Cyan
& $VenvPython (Join-Path $ProjectRoot "scripts\create-synthetic-samples.py")

$Tesseract = Get-Command tesseract -ErrorAction SilentlyContinue
if (-not $Tesseract) {
    $CommonTesseract = "C:\Program Files\Tesseract-OCR\tesseract.exe"
    if (Test-Path -LiteralPath $CommonTesseract) {
        Write-Host "Tesseract found at $CommonTesseract" -ForegroundColor Green
        Write-Host "Set this path from PayTracker Settings if OCR does not detect it automatically."
    } else {
        Write-Warning @"
Tesseract OCR was not found. Manual entry remains fully functional.
Install the Windows Tesseract build, then set its full executable path in Settings.
Typical path: C:\Program Files\Tesseract-OCR\tesseract.exe
"@
    }
} else {
    Write-Host "Tesseract OCR found: $($Tesseract.Source)" -ForegroundColor Green
}

Write-Host ""
Write-Host "PayTracker setup complete." -ForegroundColor Green
Write-Host "Laptop-only: .\start-paytracker.ps1"
Write-Host "Trusted private Wi-Fi: .\start-paytracker.ps1 -Lan"
