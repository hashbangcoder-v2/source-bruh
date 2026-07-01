param(
    [string] $Alias = "source-bruh-release",
    [string] $StoreFile = "app/source-bruh-release.keystore"
)

$ErrorActionPreference = "Stop"

$scriptRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$androidRoot = Resolve-Path (Join-Path $scriptRoot "..\android")
$storePath = Join-Path $androidRoot $StoreFile
$propertiesPath = Join-Path $androidRoot "keystore.properties"

if (Test-Path $storePath) {
    throw "Keystore already exists: $storePath"
}

if (Test-Path $propertiesPath) {
    throw "Signing properties already exist: $propertiesPath"
}

function Read-PlainPassword([string] $Prompt) {
    $secure = Read-Host $Prompt -AsSecureString
    $bstr = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($secure)
    try {
        return [Runtime.InteropServices.Marshal]::PtrToStringBSTR($bstr)
    }
    finally {
        [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($bstr)
    }
}

$storePassword = Read-PlainPassword "Keystore password"
$keyPassword = Read-PlainPassword "Key password"

if (-not $storePassword -or -not $keyPassword) {
    throw "Passwords cannot be empty."
}

$javaHomeKeytool = if ($env:JAVA_HOME) { Join-Path $env:JAVA_HOME "bin\keytool.exe" } else { "" }
$keytool = if ($javaHomeKeytool -and (Test-Path $javaHomeKeytool)) { $javaHomeKeytool } else { "keytool" }

New-Item -ItemType Directory -Force -Path (Split-Path -Parent $storePath) | Out-Null

& $keytool -genkeypair `
    -v `
    -storetype PKCS12 `
    -keystore $storePath `
    -alias $Alias `
    -keyalg RSA `
    -keysize 2048 `
    -validity 10000 `
    -storepass $storePassword `
    -keypass $keyPassword `
    -dname "CN=Source Bruh, O=Source Bruh, C=US"

@(
    "storeFile=$StoreFile"
    "storePassword=$storePassword"
    "keyAlias=$Alias"
    "keyPassword=$keyPassword"
) | Set-Content -Path $propertiesPath -Encoding ascii

Write-Host ""
Write-Host "Created:"
Write-Host "  $storePath"
Write-Host "  $propertiesPath"
Write-Host ""
Write-Host "Release fingerprints:"
& $keytool -list -v -keystore $storePath -alias $Alias -storepass $storePassword
