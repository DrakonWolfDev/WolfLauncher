[CmdletBinding()]
param(
    [string]$DestinationRoot = "",
    [string]$Version = "6.7.3"
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

$expectedVersion = "6.7.3"
$expectedSha256 = "9c73c3bae7ed48d44112a0f48e66742c00090bdb5bef71d9d3c056c66e97b732"
if ($Version -ne $expectedVersion) {
    throw "Only the verified Inno Setup $expectedVersion compiler is supported."
}

$projectRoot = Split-Path -Parent $PSScriptRoot
if (-not $DestinationRoot) {
    $DestinationRoot = Join-Path $projectRoot "build\tools\inno-setup-$Version"
}
$DestinationRoot = [System.IO.Path]::GetFullPath($DestinationRoot)
$compilerPath = Join-Path $DestinationRoot "ISCC.exe"
$versionMarker = Join-Path $DestinationRoot "wolflauncher-tool.json"
if (
    (Test-Path -LiteralPath $compilerPath -PathType Leaf) -and
    (Test-Path -LiteralPath $versionMarker -PathType Leaf)
) {
    $marker = Get-Content -LiteralPath $versionMarker -Raw | ConvertFrom-Json
    $compilerSha256 = (Get-FileHash -LiteralPath $compilerPath -Algorithm SHA256).Hash.ToLowerInvariant()
    if (
        $marker.version -eq $Version -and
        $marker.installer_sha256 -eq $expectedSha256 -and
        $marker.PSObject.Properties.Name -contains "compiler_sha256" -and
        $marker.compiler_sha256 -eq $compilerSha256
    ) {
        Write-Output $compilerPath
        exit 0
    }
}

$downloadUrl = "https://github.com/jrsoftware/issrc/releases/download/is-6_7_3/innosetup-$Version.exe"
$installerPath = Join-Path ([System.IO.Path]::GetTempPath()) "innosetup-$Version-$([guid]::NewGuid()).exe"
try {
    Invoke-WebRequest -Uri $downloadUrl -OutFile $installerPath
    $actualSha256 = (Get-FileHash -LiteralPath $installerPath -Algorithm SHA256).Hash.ToLowerInvariant()
    if ($actualSha256 -ne $expectedSha256) {
        throw "Inno Setup download hash mismatch: expected $expectedSha256, received $actualSha256."
    }

    New-Item -ItemType Directory -Path $DestinationRoot -Force | Out-Null
    $arguments = @(
        "/VERYSILENT",
        "/SUPPRESSMSGBOXES",
        "/NORESTART",
        "/CURRENTUSER",
        "/DIR=$DestinationRoot"
    )
    $process = Start-Process -FilePath $installerPath -ArgumentList $arguments -Wait -PassThru
    if ($process.ExitCode -ne 0) {
        throw "Inno Setup installation failed with exit code $($process.ExitCode)."
    }
    if (-not (Test-Path -LiteralPath $compilerPath -PathType Leaf)) {
        throw "Inno Setup installed without the expected compiler: $compilerPath"
    }
    $historyPath = Join-Path $DestinationRoot "whatsnew.htm"
    if (
        -not (Test-Path -LiteralPath $historyPath -PathType Leaf) -or
        -not (Select-String -LiteralPath $historyPath -SimpleMatch "name=`"$Version`"" -Quiet)
    ) {
        throw "The installed compiler did not contain the expected $Version release marker."
    }
    $compilerSha256 = (Get-FileHash -LiteralPath $compilerPath -Algorithm SHA256).Hash.ToLowerInvariant()
    $marker = [ordered]@{
        version = $Version
        installer_sha256 = $expectedSha256
        compiler_sha256 = $compilerSha256
    }
    [System.IO.File]::WriteAllText(
        $versionMarker,
        ($marker | ConvertTo-Json -Compress) + "`n",
        [System.Text.Encoding]::UTF8
    )
    Write-Output $compilerPath
}
finally {
    Remove-Item -LiteralPath $installerPath -Force -ErrorAction SilentlyContinue
}
