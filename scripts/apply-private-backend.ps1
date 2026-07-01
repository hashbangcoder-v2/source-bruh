[CmdletBinding()]
param(
    [string] $OverlayDir = ".local/firebase-backend"
)

$ErrorActionPreference = "Stop"

$repoRoot = Resolve-Path (Join-Path $PSScriptRoot "..")
$overlayRoot = Join-Path $repoRoot $OverlayDir

if (-not (Test-Path -LiteralPath $overlayRoot -PathType Container)) {
    throw "Private backend overlay not found: $overlayRoot"
}

$requiredFiles = @(
    @{ Source = ".firebaserc"; Destination = ".firebaserc" },
    @{ Source = "functions.config.yaml"; Destination = "functions/config.yaml" },
    @{ Source = "react-native.config.ts"; Destination = "react-native/src/config.ts" },
    @{ Source = "google-services.json"; Destination = "react-native/android/app/google-services.json" }
)

$optionalFiles = @(
    @{ Source = "gcloud-service-account.json"; Destination = "functions/gcloud-service-account.json" },
    @{ Source = "keystore.properties"; Destination = "react-native/android/keystore.properties" },
    @{ Source = "source-bruh-release.keystore"; Destination = "react-native/android/app/source-bruh-release.keystore" }
)

function Copy-OverlayFile {
    param(
        [string] $SourceRelativePath,
        [string] $DestinationRelativePath,
        [bool] $Required
    )

    $source = Join-Path $overlayRoot $SourceRelativePath
    $destination = Join-Path $repoRoot $DestinationRelativePath

    if (-not (Test-Path -LiteralPath $source -PathType Leaf)) {
        if ($Required) {
            throw "Missing required private backend file: $source"
        }
        Write-Host "Skipping optional file: $SourceRelativePath"
        return
    }

    $destinationDir = Split-Path -Parent $destination
    if ($destinationDir -and -not (Test-Path -LiteralPath $destinationDir -PathType Container)) {
        New-Item -ItemType Directory -Path $destinationDir | Out-Null
    }

    Copy-Item -LiteralPath $source -Destination $destination -Force
    Write-Host "Applied $SourceRelativePath -> $DestinationRelativePath"
}

foreach ($file in $requiredFiles) {
    Copy-OverlayFile `
        -SourceRelativePath $file.Source `
        -DestinationRelativePath $file.Destination `
        -Required $true
}

foreach ($file in $optionalFiles) {
    Copy-OverlayFile `
        -SourceRelativePath $file.Source `
        -DestinationRelativePath $file.Destination `
        -Required $false
}

Write-Host ""
Write-Host "Private backend overlay applied."
Write-Host "Review git status before committing. Do not stage copied private config files."
