$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot
& (Join-Path $PSScriptRoot 'spawn_183_validate_installer.ps1') `
    -PackageDirectory (Join-Path $root 'delivery/SOH-EXTREME-1.8.3-spawn-placement') `
    -OriginalArchive (Join-Path $root 'upload/haha.zip') `
    -PreviousPackageArchives @(
        (Join-Path $PSScriptRoot 'installer_revision_1_reference.zip'),
        (Join-Path $root 'delivery/SOH-EXTREME-1.8.1-coupled-entrances.zip'),
        (Join-Path $root 'delivery/SOH-EXTREME-1.8.2-overworld-entrances.zip')
    ) `
    -ExpectedPayloadCount 27 `
    -ExpectedVersion '1.8.3' `
    -ResultPath (Join-Path $PSScriptRoot 'spawn_183_installer_validation.json')
