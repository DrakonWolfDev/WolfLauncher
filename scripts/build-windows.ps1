[CmdletBinding()]
param(
    [string]$Python = "python",
    [string]$Npm = "npm",
    [string]$Node = "node",
    [string]$ArtifactLabel = "windows-x64"
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

function Get-Sha256Digest([string]$Path) {
    $algorithm = [System.Security.Cryptography.SHA256]::Create()
    $stream = [System.IO.File]::OpenRead($Path)
    try {
        return -join ($algorithm.ComputeHash($stream) | ForEach-Object { $_.ToString("x2") })
    }
    finally {
        $stream.Dispose()
        $algorithm.Dispose()
    }
}

if ($env:OS -ne "Windows_NT") {
    throw "The Windows artifact must be built on Windows."
}

$projectRoot = Split-Path -Parent $PSScriptRoot
$distRoot = Join-Path $projectRoot "dist\windows"
$workRoot = Join-Path $projectRoot "build\windows"
$bundleRoot = Join-Path $distRoot "WolfLauncher"
$iconPath = Join-Path $workRoot "wolflauncher.ico"
$npmProject = Join-Path $projectRoot "packaging\npm"
$environmentKeys = @(
    "WOLFLAUNCHER_NODE_EXE",
    "WOLFLAUNCHER_NODE_MODULES",
    "WOLFLAUNCHER_ICON_PATH",
    "APPDATA",
    "LOCALAPPDATA",
    "QT_QPA_PLATFORM",
    "WOLFLAUNCHER_SMOKE_TEST",
    "WOLFLAUNCHER_SMOKE_REQUIRE_KEYRING"
)
$originalEnvironment = @{}
foreach ($key in $environmentKeys) {
    $originalEnvironment[$key] = [System.Environment]::GetEnvironmentVariable($key, "Process")
}

Push-Location $projectRoot
try {
    foreach ($tool in @($Npm, $Node)) {
        if (-not (Get-Command -Name $tool -CommandType Application -ErrorAction SilentlyContinue)) {
            throw "Required Node.js build tool '$tool' was not found. Install the pinned Node.js 24.14.0 Windows runtime (which includes npm), reopen PowerShell, then rerun this command."
        }
    }

    & $Npm ci --prefix $npmProject --ignore-scripts
    if ($LASTEXITCODE -ne 0) {
        throw "npm ci failed."
    }

    & $Python "scripts\render-windows-icon.py" "wolflauncher\assets\wolf-mark.svg" $iconPath
    if ($LASTEXITCODE -ne 0) {
        throw "Windows icon rendering failed."
    }

    $nodePath = (& $Node -p "process.execPath").Trim()
    if (-not (Test-Path -LiteralPath $nodePath -PathType Leaf)) {
        throw "Could not resolve the Node.js executable."
    }

    $env:WOLFLAUNCHER_NODE_EXE = $nodePath
    $env:WOLFLAUNCHER_NODE_MODULES = Join-Path $npmProject "node_modules"
    $env:WOLFLAUNCHER_ICON_PATH = $iconPath

    & $Python -m PyInstaller `
        --noconfirm `
        --clean `
        --distpath $distRoot `
        --workpath $workRoot `
        "packaging\windows\WolfLauncher.spec"
    if ($LASTEXITCODE -ne 0) {
        throw "PyInstaller build failed."
    }

    Copy-Item -LiteralPath "README.md" -Destination $bundleRoot
    Copy-Item -LiteralPath "LICENSE" -Destination $bundleRoot
    Copy-Item -LiteralPath "THIRD_PARTY_NOTICES.md" -Destination $bundleRoot

    $version = (& $Python -c "from wolflauncher import __version__; print(__version__)").Trim()
    if (-not $version) {
        throw "Could not determine the WolfLauncher version."
    }

    $smokeRoot = Join-Path ([System.IO.Path]::GetTempPath()) ("wolflauncher-smoke-" + [guid]::NewGuid())
    New-Item -ItemType Directory -Path $smokeRoot | Out-Null
    try {
        $env:APPDATA = Join-Path $smokeRoot "config"
        $env:LOCALAPPDATA = Join-Path $smokeRoot "data"
        $env:QT_QPA_PLATFORM = "offscreen"
        $env:WOLFLAUNCHER_SMOKE_TEST = "1"
        $env:WOLFLAUNCHER_SMOKE_REQUIRE_KEYRING = "1"
        $process = Start-Process -FilePath (Join-Path $bundleRoot "WolfLauncher.exe") -PassThru
        try {
            Wait-Process -Id $process.Id -Timeout 45 -ErrorAction Stop
        }
        catch {
            if (-not $process.HasExited) {
                Stop-Process -Id $process.Id -Force -ErrorAction SilentlyContinue
            }
            throw "Packaged startup smoke test did not exit within 45 seconds."
        }
        $process.Refresh()
        if ($process.ExitCode -ne 0) {
            throw "Packaged startup smoke test exited with code $($process.ExitCode)."
        }
    }
    finally {
        if ($smokeRoot.StartsWith([System.IO.Path]::GetTempPath(), [System.StringComparison]::OrdinalIgnoreCase)) {
            Remove-Item -LiteralPath $smokeRoot -Recurse -Force -ErrorAction SilentlyContinue
        }
    }

    $archiveName = "wolflauncher-$version-$ArtifactLabel.zip"
    $archivePath = Join-Path $distRoot $archiveName
    if (Test-Path -LiteralPath $archivePath) {
        Remove-Item -LiteralPath $archivePath -Force
    }
    Compress-Archive -LiteralPath $bundleRoot -DestinationPath $archivePath -CompressionLevel Optimal

    $hash = Get-Sha256Digest $archivePath
    $hashPath = "$archivePath.sha256"
    [System.IO.File]::WriteAllText($hashPath, "$hash  $archiveName`n", [System.Text.Encoding]::ASCII)

    Write-Host "Built $archivePath"
    Write-Host "SHA256 $hash"
}
finally {
    Pop-Location
    foreach ($key in $environmentKeys) {
        $value = $originalEnvironment[$key]
        if ($null -eq $value) {
            [System.Environment]::SetEnvironmentVariable($key, $null, "Process")
        }
        else {
            [System.Environment]::SetEnvironmentVariable($key, $value, "Process")
        }
    }
}
