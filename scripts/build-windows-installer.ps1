[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [string]$Iscc,
    [string]$Python = "python",
    [string]$BundleRoot = "",
    [string]$OutputRoot = "",
    [string]$ArtifactLabel = "windows-x64"
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

if ($env:OS -ne "Windows_NT") {
    throw "The Windows installer must be built on Windows."
}

$projectRoot = Split-Path -Parent $PSScriptRoot
if (-not $BundleRoot) {
    $BundleRoot = Join-Path $projectRoot "dist\windows\WolfLauncher"
}
if (-not $OutputRoot) {
    $OutputRoot = Join-Path $projectRoot "dist\windows"
}
$BundleRoot = [System.IO.Path]::GetFullPath($BundleRoot)
$OutputRoot = [System.IO.Path]::GetFullPath($OutputRoot)
$Iscc = [System.IO.Path]::GetFullPath($Iscc)
$iconPath = Join-Path $projectRoot "build\windows\wolflauncher.ico"
$installerScript = Join-Path $projectRoot "packaging\windows\WolfLauncher.iss"

foreach ($requiredFile in @(
    $Iscc,
    (Join-Path $BundleRoot "WolfLauncher.exe"),
    (Join-Path $BundleRoot "LICENSE"),
    $iconPath,
    $installerScript
)) {
    if (-not (Test-Path -LiteralPath $requiredFile -PathType Leaf)) {
        throw "Required installer input is missing: $requiredFile"
    }
}

$version = (& $Python -c "from wolflauncher import __version__; print(__version__)").Trim()
if (-not $version) {
    throw "Could not determine the WolfLauncher version."
}
$numericParts = [regex]::Matches($version, "\d+") | Select-Object -First 3 | ForEach-Object { $_.Value }
if ($numericParts.Count -ne 3) {
    throw "Could not derive a Windows numeric version from $version."
}
$numericVersion = ($numericParts + @("0")) -join "."
New-Item -ItemType Directory -Path $OutputRoot -Force | Out-Null
$installerName = "wolflauncher-$version-setup-$ArtifactLabel.exe"
$installerPath = Join-Path $OutputRoot $installerName
Remove-Item -LiteralPath $installerPath -Force -ErrorAction SilentlyContinue

& $Iscc `
    "/Qp" `
    "/DAppVersion=$version" `
    "/DNumericVersion=$numericVersion" `
    "/DBundleRoot=$BundleRoot" `
    "/DOutputRoot=$OutputRoot" `
    "/DSetupIcon=$iconPath" `
    "/DArtifactLabel=$ArtifactLabel" `
    $installerScript
if ($LASTEXITCODE -ne 0) {
    throw "Inno Setup compilation failed."
}
if (-not (Test-Path -LiteralPath $installerPath -PathType Leaf)) {
    throw "Inno Setup did not produce the expected installer: $installerPath"
}

$hash = (Get-FileHash -LiteralPath $installerPath -Algorithm SHA256).Hash.ToLowerInvariant()
$hashPath = "$installerPath.sha256"
[System.IO.File]::WriteAllText($hashPath, "$hash  $installerName`n", [System.Text.Encoding]::ASCII)
Write-Host "Built $installerPath"
Write-Host "SHA256 $hash"
