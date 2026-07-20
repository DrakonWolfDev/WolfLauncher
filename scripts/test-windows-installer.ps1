[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [string]$InstallerPath
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

if ($env:OS -ne "Windows_NT") {
    throw "The Windows installer smoke test must run on Windows."
}

$InstallerPath = [System.IO.Path]::GetFullPath($InstallerPath)
if (-not (Test-Path -LiteralPath $InstallerPath -PathType Leaf)) {
    throw "Installer not found: $InstallerPath"
}

$tempRoot = [System.IO.Path]::GetFullPath([System.IO.Path]::GetTempPath())
$smokeRoot = Join-Path $tempRoot ("wolflauncher-installer-smoke-" + [guid]::NewGuid())
$installRoot = Join-Path $smokeRoot "installed"
$configRoot = Join-Path $smokeRoot "profile\config"
$dataRoot = Join-Path $smokeRoot "profile\data"
$configSentinel = Join-Path $configRoot "wolflauncher\preserve-config.txt"
$dataSentinel = Join-Path $dataRoot "wolflauncher\preserve-data.txt"

function Invoke-Setup([string]$Executable, [string[]]$Arguments) {
    $process = Start-Process -FilePath $Executable -ArgumentList $Arguments -Wait -PassThru
    if ($process.ExitCode -ne 0) {
        throw "$Executable exited with code $($process.ExitCode)."
    }
}

function Invoke-ApplicationSmoke([string]$Executable) {
    $originalAppData = $env:APPDATA
    $originalLocalAppData = $env:LOCALAPPDATA
    $originalQtPlatform = $env:QT_QPA_PLATFORM
    $originalSmokeTest = $env:WOLFLAUNCHER_SMOKE_TEST
    $originalSmokeKeyring = $env:WOLFLAUNCHER_SMOKE_REQUIRE_KEYRING
    try {
        $env:APPDATA = $configRoot
        $env:LOCALAPPDATA = $dataRoot
        $env:QT_QPA_PLATFORM = "offscreen"
        $env:WOLFLAUNCHER_SMOKE_TEST = "1"
        $env:WOLFLAUNCHER_SMOKE_REQUIRE_KEYRING = "1"
        $process = Start-Process -FilePath $Executable -PassThru
        try {
            Wait-Process -Id $process.Id -Timeout 45 -ErrorAction Stop
        }
        catch {
            if (-not $process.HasExited) {
                Stop-Process -Id $process.Id -Force -ErrorAction SilentlyContinue
            }
            throw "Installed application smoke test did not exit within 45 seconds."
        }
        $process.Refresh()
        if ($process.ExitCode -ne 0) {
            throw "Installed application smoke test exited with code $($process.ExitCode)."
        }
    }
    finally {
        $env:APPDATA = $originalAppData
        $env:LOCALAPPDATA = $originalLocalAppData
        $env:QT_QPA_PLATFORM = $originalQtPlatform
        $env:WOLFLAUNCHER_SMOKE_TEST = $originalSmokeTest
        $env:WOLFLAUNCHER_SMOKE_REQUIRE_KEYRING = $originalSmokeKeyring
    }
}

New-Item -ItemType Directory -Path (Split-Path -Parent $configSentinel) -Force | Out-Null
New-Item -ItemType Directory -Path (Split-Path -Parent $dataSentinel) -Force | Out-Null
[System.IO.File]::WriteAllText($configSentinel, "preserve config")
[System.IO.File]::WriteAllText($dataSentinel, "preserve data")
$uninstallCompleted = $false

try {
    $installArguments = @(
        "/VERYSILENT",
        "/SUPPRESSMSGBOXES",
        "/NORESTART",
        "/DIR=$installRoot"
    )
    Invoke-Setup $InstallerPath $installArguments

    $applicationPath = Join-Path $installRoot "WolfLauncher.exe"
    $uninstallerPath = Join-Path $installRoot "unins000.exe"
    foreach ($requiredFile in @($applicationPath, $uninstallerPath)) {
        if (-not (Test-Path -LiteralPath $requiredFile -PathType Leaf)) {
            throw "Installed file is missing: $requiredFile"
        }
    }
    Invoke-ApplicationSmoke $applicationPath

    Invoke-Setup $InstallerPath $installArguments
    Invoke-ApplicationSmoke $applicationPath

    Invoke-Setup $uninstallerPath @("/VERYSILENT", "/SUPPRESSMSGBOXES", "/NORESTART")
    $uninstallCompleted = $true
    if (Test-Path -LiteralPath $applicationPath) {
        throw "Uninstall left the application executable behind."
    }
    foreach ($sentinel in @($configSentinel, $dataSentinel)) {
        if (-not (Test-Path -LiteralPath $sentinel -PathType Leaf)) {
            throw "Uninstall removed user-owned data: $sentinel"
        }
    }
    Write-Host "Installer reinstall/start/uninstall smoke test passed; user data was preserved."
}
finally {
    $uninstallerPath = Join-Path $installRoot "unins000.exe"
    if (-not $uninstallCompleted -and (Test-Path -LiteralPath $uninstallerPath -PathType Leaf)) {
        try {
            Invoke-Setup $uninstallerPath @("/VERYSILENT", "/SUPPRESSMSGBOXES", "/NORESTART")
        }
        catch {
            Write-Warning "Installer smoke cleanup could not run the uninstaller: $_"
        }
    }
    $resolvedSmokeRoot = [System.IO.Path]::GetFullPath($smokeRoot)
    if ($resolvedSmokeRoot.StartsWith($tempRoot, [System.StringComparison]::OrdinalIgnoreCase)) {
        Remove-Item -LiteralPath $resolvedSmokeRoot -Recurse -Force -ErrorAction SilentlyContinue
    }
}
