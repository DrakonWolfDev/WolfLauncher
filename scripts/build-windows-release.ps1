[CmdletBinding()]
param(
    [string]$Python = ""
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

$projectRoot = Split-Path -Parent $PSScriptRoot
if (-not $Python) {
    $Python = Join-Path $projectRoot ".venv\Scripts\python.exe"
}
$Python = [System.IO.Path]::GetFullPath($Python)
if (-not (Test-Path -LiteralPath $Python -PathType Leaf)) {
    throw "Windows release Python was not found: $Python. Create .venv with Python 3.12 and install requirements-windows-release.txt first."
}

Push-Location $projectRoot
try {
    Write-Host "Building WolfLauncher portable Windows ZIP..."
    & (Join-Path $PSScriptRoot "build-windows.ps1") -Python $Python
    if ($LASTEXITCODE -ne 0) {
        throw "Portable Windows build failed."
    }

    Write-Host "Ensuring hash-pinned Inno Setup compiler is available..."
    $iscc = (& (Join-Path $PSScriptRoot "install-inno-setup.ps1")).Trim()
    if ($LASTEXITCODE -ne 0 -or -not (Test-Path -LiteralPath $iscc -PathType Leaf)) {
        throw "Inno Setup compiler preparation failed."
    }

    Write-Host "Building WolfLauncher Inno Setup installer..."
    & (Join-Path $PSScriptRoot "build-windows-installer.ps1") -Iscc $iscc -Python $Python
    if ($LASTEXITCODE -ne 0) {
        throw "Inno Setup installer build failed."
    }

    $version = (& $Python -c "from wolflauncher import __version__; print(__version__)").Trim()
    $outputRoot = Join-Path $projectRoot "dist\windows"
    Write-Host "Completed:"
    foreach ($name in @(
        "wolflauncher-$version-windows-x64.zip",
        "wolflauncher-$version-windows-x64.zip.sha256",
        "wolflauncher-$version-setup-windows-x64.exe",
        "wolflauncher-$version-setup-windows-x64.exe.sha256"
    )) {
        $artifact = Join-Path $outputRoot $name
        if (Test-Path -LiteralPath $artifact -PathType Leaf) {
            Write-Host $artifact
        }
    }
}
finally {
    Pop-Location
}
