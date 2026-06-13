$ErrorActionPreference = "Continue"

$legacyPackages = @(
  "com.sourcebruh.android"
)

$adbCandidates = @()
if ($env:ANDROID_HOME) {
  $adbCandidates += (Join-Path $env:ANDROID_HOME "platform-tools\adb.exe")
}
if ($env:ANDROID_SDK_ROOT) {
  $adbCandidates += (Join-Path $env:ANDROID_SDK_ROOT "platform-tools\adb.exe")
}
$adbCandidates += (Join-Path $env:LOCALAPPDATA "Android\Sdk\platform-tools\adb.exe")

$adb = $adbCandidates | Where-Object { Test-Path $_ } | Select-Object -First 1
if (-not $adb) {
  $adbCommand = Get-Command adb -ErrorAction SilentlyContinue
  if ($adbCommand) {
    $adb = $adbCommand.Source
  }
}

if (-not $adb) {
  Write-Host "[android-clean] adb not found; skipping stale package cleanup."
  exit 0
}

$deviceLines = & $adb devices 2>$null | Select-Object -Skip 1
$devices = @(
  $deviceLines |
    ForEach-Object {
      if ($_ -match "^(\S+)\s+device$") {
        $Matches[1]
      }
    }
)

if ($devices.Count -eq 0) {
  Write-Host "[android-clean] no connected adb device; skipping stale package cleanup."
  exit 0
}

foreach ($device in $devices) {
  foreach ($packageName in $legacyPackages) {
    Write-Host "[android-clean] removing $packageName from $device if present..."
    $output = & $adb -s $device uninstall $packageName 2>&1
    if ($LASTEXITCODE -eq 0) {
      Write-Host "[android-clean] removed $packageName from $device."
    } elseif ($output -match "not installed|Unknown package|DELETE_FAILED_INTERNAL_ERROR") {
      Write-Host "[android-clean] $packageName is not installed on $device."
    } else {
      Write-Host "[android-clean] cleanup warning for ${packageName} on ${device}: $output"
    }
  }
}
