$ErrorActionPreference = 'Stop'

$Root = Split-Path -Parent $PSScriptRoot
$BaseApworld = Join-Path $Root 'apworld\soh_extreme.apworld'
$OutApworld = Join-Path $Root 'apworld\soh_extreme-0.11.2-standalone.apworld'
$InstallPath = 'C:\ProgramData\Archipelago\custom_worlds\soh_extreme.apworld'
$StockUrl = 'https://github.com/HarbourMasters/Archipelago-SoH/releases/download/Soh_1.4.2/oot_soh.apworld'

if (-not (Test-Path $BaseApworld)) {
    throw "Base APWorld not found: $BaseApworld"
}

$temp = Join-Path ([System.IO.Path]::GetTempPath()) ('soh-extreme-vendor-' + [Guid]::NewGuid().ToString('N'))
$customDir = Join-Path $temp 'custom'
$stockDir = Join-Path $temp 'stock'
$stockFile = Join-Path $temp 'oot_soh.apworld'
$stockZip = Join-Path $temp 'oot_soh.zip'
$customZip = Join-Path $temp 'soh_extreme.zip'
$outZip = Join-Path $temp 'soh_extreme-standalone.zip'

try {
    New-Item -ItemType Directory -Force -Path $customDir, $stockDir | Out-Null

    Write-Host '[1/6] Downloading the official SoH 1.4.2 APWorld source bundle...'
    Invoke-WebRequest -Uri $StockUrl -OutFile $stockFile -UseBasicParsing

    Write-Host '[2/6] Extracting SOH-EXTREME and stock SoH modules...'
    Copy-Item $BaseApworld $customZip
    Copy-Item $stockFile $stockZip
    Expand-Archive -LiteralPath $customZip -DestinationPath $customDir -Force
    Expand-Archive -LiteralPath $stockZip -DestinationPath $stockDir -Force

    $stockPkg = Join-Path $stockDir 'oot_soh'
    $extremePkg = Join-Path $customDir 'soh_extreme'
    if (-not (Test-Path $stockPkg)) { throw 'Downloaded APWorld did not contain oot_soh/.' }
    if (-not (Test-Path $extremePkg)) { throw 'Base APWorld did not contain soh_extreme/.' }

    Write-Host '[3/6] Vendoring stock helper/data modules inside SOH-EXTREME...'
    $vendorPkg = Join-Path $extremePkg '_vendor_oot_soh'
    if (Test-Path $vendorPkg) { Remove-Item -Recurse -Force $vendorPkg }
    Move-Item -LiteralPath $stockPkg -Destination $vendorPkg

    # Do not execute the stock world's __init__.py.  SOH-EXTREME only needs the
    # data/helper submodules and remains the one registered AutoWorld.
    @'
"""Private vendored Ship of Harkinian helper package used by SOH-EXTREME.

This package intentionally has an empty __init__ so importing helper modules does
not register the stock Ship of Harkinian AutoWorld.  SOH-EXTREME is standalone at
runtime and does not require worlds.oot_soh to be installed.
"""
'@ | Set-Content -LiteralPath (Join-Path $vendorPkg '__init__.py') -Encoding UTF8

    Write-Host '[4/6] Rewriting imports to the private vendor namespace...'
    $initPath = Join-Path $extremePkg '__init__.py'
    $optionsPath = Join-Path $extremePkg 'Options.py'
    $forkPath = Join-Path $extremePkg 'ForkLocations.py'

    $text = Get-Content -Raw -LiteralPath $initPath
    $text = $text.Replace('from worlds.oot_soh.', 'from ._vendor_oot_soh.')
    $text = $text.Replace('import worlds.oot_soh.DungeonRewardShuffle as DungeonRewardShuffle', 'from ._vendor_oot_soh import DungeonRewardShuffle')
    $text = $text.Replace('import worlds.oot_soh.SongShuffle as SongShuffle', 'from ._vendor_oot_soh import SongShuffle')
    $text = $text.Replace('import worlds.oot_soh.ShopItems as ShopItems', 'from ._vendor_oot_soh import ShopItems')
    Set-Content -LiteralPath $initPath -Value $text -Encoding UTF8

    foreach ($p in @($optionsPath, $forkPath)) {
        $t = Get-Content -Raw -LiteralPath $p
        $t = $t.Replace('from worlds.oot_soh.', 'from ._vendor_oot_soh.')
        Set-Content -LiteralPath $p -Value $t -Encoding UTF8
    }

    # Keep vendored modules self-contained if the upstream package contains any
    # absolute references to its original namespace.
    Get-ChildItem -LiteralPath $vendorPkg -Recurse -File -Filter '*.py' | ForEach-Object {
        # Get-Content -Raw returns $null for an empty file.  Upstream contains
        # empty Python package files, so use ReadAllText() which returns "" instead.
        $filePath = $_.FullName
        $t = [System.IO.File]::ReadAllText($filePath)
        $t = $t.Replace('from worlds.oot_soh', 'from worlds.soh_extreme._vendor_oot_soh')
        $t = $t.Replace('import worlds.oot_soh', 'import worlds.soh_extreme._vendor_oot_soh')
        [System.IO.File]::WriteAllText(
            $filePath,
            $t,
            (New-Object System.Text.UTF8Encoding($false))
        )
    }

    # Bump the SOH-EXTREME package version independently from the vendored copy.
    $manifest = Join-Path $extremePkg 'archipelago.json'
    $json = Get-Content -Raw -LiteralPath $manifest | ConvertFrom-Json
    $json.world_version = '0.11.2'
    $json | ConvertTo-Json -Depth 20 | Set-Content -LiteralPath $manifest -Encoding UTF8

    # Hard validation: reject actual Python imports that still depend on the
    # external stock world.  Do not fail on comments/docstrings that merely
    # mention its old namespace.
    $badImportPattern = '^\s*(?:from\s+worlds\.oot_soh(?:\.|\s|$)|import\s+worlds\.oot_soh(?:\.|\s|$))'
    $bad = Get-ChildItem -LiteralPath $extremePkg -Recurse -File -Filter '*.py' |
        Select-String -Pattern $badImportPattern
    if ($bad) {
        $details = ($bad | ForEach-Object { "$($_.Path):$($_.LineNumber): $($_.Line)" }) -join "`n"
        throw "Standalone validation failed; external oot_soh import remains:`n$details"
    }

    Write-Host '[5/6] Building standalone soh_extreme.apworld...'
    if (Test-Path $outZip) { Remove-Item -Force $outZip }
    Compress-Archive -Path (Join-Path $customDir '*') -DestinationPath $outZip -CompressionLevel Optimal
    Copy-Item -Force $outZip $OutApworld

    # Basic archive validation without importing Archipelago itself.
    Add-Type -AssemblyName System.IO.Compression.FileSystem
    $archive = [System.IO.Compression.ZipFile]::OpenRead($OutApworld)
    try {
        $names = $archive.Entries.FullName
        foreach ($required in @(
            'soh_extreme/__init__.py',
            'soh_extreme/Options.py',
            'soh_extreme/_vendor_oot_soh/Items.py',
            'soh_extreme/_vendor_oot_soh/Locations.py',
            'soh_extreme/_vendor_oot_soh/Regions.py',
            'soh_extreme/_vendor_oot_soh/LogicHelpers.py'
        )) {
            if ($names -notcontains $required) { throw "Standalone archive missing $required" }
        }
    } finally {
        $archive.Dispose()
    }

    Write-Host '[6/6] Installing into Archipelago custom_worlds...'
    $installDir = Split-Path -Parent $InstallPath
    New-Item -ItemType Directory -Force -Path $installDir | Out-Null
    if (Test-Path $InstallPath) {
        $backup = "$InstallPath.backup-$(Get-Date -Format yyyyMMdd-HHmmss)"
        Copy-Item -Force $InstallPath $backup
        Write-Host "Backed up existing APWorld to: $backup"
    }
    Copy-Item -Force $OutApworld $InstallPath

    Write-Host ''
    Write-Host 'SUCCESS: SOH-EXTREME 0.11.2 standalone APWorld built and installed.' -ForegroundColor Green
    Write-Host "Installed: $InstallPath"
    Write-Host 'The generated APWorld contains its private SoH helper modules and does not require oot_soh.apworld to be installed.'
}
finally {
    if (Test-Path $temp) { Remove-Item -Recurse -Force $temp }
}
