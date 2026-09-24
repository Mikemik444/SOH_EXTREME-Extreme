$ErrorActionPreference = 'Stop'
$ProgressPreference = 'SilentlyContinue'

$Root = Split-Path -Parent $PSScriptRoot
$SourceArchive = Join-Path $Root 'source\soh_extreme-source.zip'
$BuiltDir = Join-Path $Root 'built'
$BuiltApworld = Join-Path $BuiltDir 'soh_extreme.apworld'
$InstallPath = 'C:\ProgramData\Archipelago\custom_worlds\soh_extreme.apworld'
$StockUrl = 'https://github.com/HarbourMasters/Archipelago-SoH/releases/download/Soh_1.4.2/oot_soh.apworld'

if (-not (Test-Path $SourceArchive)) { throw "Missing source archive: $SourceArchive" }
New-Item -ItemType Directory -Force -Path $BuiltDir | Out-Null

$temp = Join-Path ([System.IO.Path]::GetTempPath()) ('soh-extreme-standalone-' + [Guid]::NewGuid().ToString('N'))
$customDir = Join-Path $temp 'custom'
$stockDir = Join-Path $temp 'stock'
$stockFile = Join-Path $temp 'oot_soh.apworld'
$stockZip = Join-Path $temp 'oot_soh.zip'
$customZip = Join-Path $temp 'soh_extreme.zip'
$outZip = Join-Path $temp 'soh_extreme-final.zip'

try {
    New-Item -ItemType Directory -Force -Path $customDir, $stockDir | Out-Null

    Write-Host '[1/7] Downloading official SoH 1.4.2 APWorld helper source...'
    Invoke-WebRequest -Uri $StockUrl -OutFile $stockFile -UseBasicParsing

    Write-Host '[2/7] Extracting SOH-EXTREME and helper package...'
    Copy-Item -Force $SourceArchive $customZip
    Copy-Item -Force $stockFile $stockZip
    Expand-Archive -LiteralPath $customZip -DestinationPath $customDir -Force
    Expand-Archive -LiteralPath $stockZip -DestinationPath $stockDir -Force

    $extremePkg = Join-Path $customDir 'soh_extreme'
    $stockPkg = Join-Path $stockDir 'oot_soh'
    if (-not (Test-Path $extremePkg)) { throw 'SOH-EXTREME source did not contain soh_extreme/.' }
    if (-not (Test-Path $stockPkg)) { throw 'Official helper archive did not contain oot_soh/.' }

    Write-Host '[3/7] Vendoring SoH helpers privately inside SOH-EXTREME...'
    $vendorPkg = Join-Path $extremePkg '_vendor_oot_soh'
    if (Test-Path $vendorPkg) { Remove-Item -Recurse -Force $vendorPkg }
    Move-Item -LiteralPath $stockPkg -Destination $vendorPkg

    # Never execute/register the stock SohWorld. Only its data and helper modules are used.
    #
    # A few stock helper modules (notably SongShuffle.py and ShopItems.py) import
    # SohItem from the package root (``from . import SohItem``).  Replacing the
    # stock initializer with a completely empty shim therefore breaks their import
    # chain.  Export only the harmless data class they expect; do NOT import or
    # define the stock SohWorld AutoWorld here.
    @'
"""Private SoH helper package bundled by SOH-EXTREME.

The stock AutoWorld initializer is intentionally not executed. SOH-EXTREME is
its own registered Archipelago game and does not require oot_soh.apworld.

Only compatibility symbols used by stock helper modules are re-exported here.
"""

from .Items import SohItem

__all__ = ["SohItem"]
'@ | Set-Content -LiteralPath (Join-Path $vendorPkg '__init__.py') -Encoding UTF8

    Write-Host '[4/7] Rewriting imports to the private vendor namespace...'
    $rewriteFiles = @(
        (Join-Path $extremePkg '__init__.py'),
        (Join-Path $extremePkg 'Options.py'),
        (Join-Path $extremePkg 'ForkLocations.py')
    )
    foreach ($path in $rewriteFiles) {
        if (-not (Test-Path $path)) { continue }
        $text = [System.IO.File]::ReadAllText($path)
        $text = $text.Replace('from worlds.oot_soh.', 'from ._vendor_oot_soh.')
        $text = $text.Replace('import worlds.oot_soh.DungeonRewardShuffle as DungeonRewardShuffle', 'from ._vendor_oot_soh import DungeonRewardShuffle')
        $text = $text.Replace('import worlds.oot_soh.SongShuffle as SongShuffle', 'from ._vendor_oot_soh import SongShuffle')
        $text = $text.Replace('import worlds.oot_soh.ShopItems as ShopItems', 'from ._vendor_oot_soh import ShopItems')
        [System.IO.File]::WriteAllText($path, $text, [System.Text.UTF8Encoding]::new($false))
    }

    # Any upstream absolute self-imports must point at the bundled namespace.
    Get-ChildItem -Path $vendorPkg -Recurse -Filter '*.py' | ForEach-Object {
        # Get-Content -Raw returns $null for empty Python package files (for
        # example location_access\__init__.py). Calling .Replace() on that
        # caused the 0.11.3 installer to fail at step 4. ReadAllText always
        # returns a string, including for zero-byte files.
        $vendorFile = $_.FullName
        $text = [System.IO.File]::ReadAllText($vendorFile)
        $text = $text.Replace('from worlds.oot_soh', 'from worlds.soh_extreme._vendor_oot_soh')
        $text = $text.Replace('import worlds.oot_soh', 'import worlds.soh_extreme._vendor_oot_soh')
        # Stock SongShuffle.py / ShopItems.py import SohItem from the package
        # root. Point those imports directly at Items.py so the private vendor
        # package does not need to execute the stock AutoWorld initializer.
        $text = $text.Replace('from . import SohItem', 'from .Items import SohItem')
        [System.IO.File]::WriteAllText($vendorFile, $text, [System.Text.UTF8Encoding]::new($false))
    }

    $manifest = Join-Path $extremePkg 'archipelago.json'
    $json = Get-Content -Raw -LiteralPath $manifest | ConvertFrom-Json
    $json.world_version = '0.11.9'
    $json | ConvertTo-Json -Depth 20 | Set-Content -LiteralPath $manifest -Encoding UTF8

    Write-Host '[5/7] Validating standalone package before build...'
    $bad = Get-ChildItem -Path $extremePkg -Recurse -Filter '*.py' |
        Select-String -Pattern 'worlds\.oot_soh'
    if ($bad) {
        $details = ($bad | ForEach-Object { "$($_.Path):$($_.LineNumber): $($_.Line)" }) -join "`n"
        throw "Standalone validation failed; direct worlds.oot_soh dependency remains:`n$details"
    }

    foreach ($required in @(
        'Items.py', 'Locations.py', 'Enums.py', 'Options.py', 'LogicHelpers.py',
        'Regions.py', 'ItemPool.py', 'KeyShuffle.py', 'ShopItems.py',
        'SongShuffle.py', 'DungeonRewardShuffle.py', 'Hints.py'
    )) {
        if (-not (Test-Path (Join-Path $vendorPkg $required))) {
            throw "Vendored helper package is missing $required"
        }
    }
    foreach ($requiredDir in @('location_access', 'location_access\dungeons', 'location_access\overworld')) {
        if (-not (Test-Path (Join-Path $vendorPkg $requiredDir))) {
            throw "Vendored helper package is missing $requiredDir"
        }
    }

    # Validate every custom Regions.X reference against the exact Regions enum
    # bundled from the official SoH helper package.  This catches typos / stale
    # region names before an APWorld is installed (0.11.7 crashed at set_rules
    # because DEATH_MOUNTAIN_ROCKFALL and DMC_POTS_ENTRY are not real enums).
    $enumText = [System.IO.File]::ReadAllText((Join-Path $vendorPkg 'Enums.py'))
    $regionsBlock = [regex]::Match($enumText, '(?ms)^class Regions\(StrEnum\):\s*(.*?)(?=^class\s)')
    if (-not $regionsBlock.Success) {
        throw 'Could not parse Regions enum from vendored Enums.py.'
    }
    $validRegions = New-Object 'System.Collections.Generic.HashSet[string]'
    [regex]::Matches($regionsBlock.Groups[1].Value, '(?m)^\s{4}([A-Z][A-Z0-9_]*)\s*=') | ForEach-Object {
        [void]$validRegions.Add($_.Groups[1].Value)
    }
    $missingRegionRefs = New-Object 'System.Collections.Generic.List[string]'
    Get-ChildItem -Path $extremePkg -Recurse -Filter '*.py' | Where-Object {
        -not $_.FullName.StartsWith($vendorPkg, [System.StringComparison]::OrdinalIgnoreCase)
    } | ForEach-Object {
        $customText = [System.IO.File]::ReadAllText($_.FullName)
        [regex]::Matches($customText, 'Regions\.([A-Z][A-Z0-9_]*)') | ForEach-Object {
            $name = $_.Groups[1].Value
            if (-not $validRegions.Contains($name)) {
                $relative = $null
                try { $relative = [System.IO.Path]::GetRelativePath($extremePkg, $_.Path) } catch { $relative = $_.Path }
                $missingRegionRefs.Add($name)
            }
        }
    }
    if ($missingRegionRefs.Count -gt 0) {
        $uniqueMissing = ($missingRegionRefs | Sort-Object -Unique) -join ', '
        throw "SOH-EXTREME references unknown Regions enum value(s): $uniqueMissing"
    }

    # Validate the package-root compatibility contract that broke 0.11.5.
    $vendorInit = [System.IO.File]::ReadAllText((Join-Path $vendorPkg '__init__.py'))
    if ($vendorInit -notmatch 'from \.Items import SohItem') {
        throw 'Vendored helper initializer does not export SohItem.'
    }
    $badRootSohItem = Get-ChildItem -Path $vendorPkg -Recurse -Filter '*.py' |
        Select-String -SimpleMatch 'from . import SohItem'
    if ($badRootSohItem) {
        $details = ($badRootSohItem | ForEach-Object { "$($_.Path):$($_.LineNumber): $($_.Line)" }) -join "`n"
        throw "Vendored helper still contains package-root SohItem imports:`n$details"
    }

    $extremeInit = [System.IO.File]::ReadAllText((Join-Path $extremePkg '__init__.py'))
    foreach ($requiredStateSymbol in @(
        'self._soh_stale = {}',
        'self.soh_heart_count = {}',
        'def _soh_invalidate',
        'def _soh_update_age_reachable_regions',
        'def _soh_can_reach_as_age'
    )) {
        if (-not $extremeInit.Contains($requiredStateSymbol)) {
            throw "SOH-EXTREME standalone CollectionState support is missing: $requiredStateSymbol"
        }
    }

    Write-Host '[6/7] Building final soh_extreme.apworld...'
    if (Test-Path $outZip) { Remove-Item -Force $outZip }

    # Windows PowerShell 5.1 Compress-Archive can store directory separators as
    # backslashes.  Python/zipimport and Archipelago APWorld packages require
    # normal ZIP forward-slash entry names.  Build the archive explicitly so
    # every entry is portable and importable.
    Add-Type -AssemblyName System.IO.Compression
    Add-Type -AssemblyName System.IO.Compression.FileSystem
    $outStream = [System.IO.File]::Open($outZip, [System.IO.FileMode]::CreateNew)
    $zip = New-Object -TypeName System.IO.Compression.ZipArchive -ArgumentList @($outStream, [System.IO.Compression.ZipArchiveMode]::Create, $false)
    try {
        Get-ChildItem -Path $customDir -Recurse -File | ForEach-Object {
            $relative = $_.FullName.Substring($customDir.Length)
            $relative = $relative.TrimStart([char[]]@([char]92, [char]47))
            $entryName = $relative.Replace([char]92, [char]47)
            $entry = $zip.CreateEntry($entryName, [System.IO.Compression.CompressionLevel]::Optimal)
            $entryStream = $entry.Open()
            $inputStream = [System.IO.File]::OpenRead($_.FullName)
            try {
                $inputStream.CopyTo($entryStream)
            }
            finally {
                $inputStream.Dispose()
                $entryStream.Dispose()
            }
        }
    }
    finally {
        $zip.Dispose()
        $outStream.Dispose()
    }
    Copy-Item -Force $outZip $BuiltApworld

    # Validate archive contents, not just the staging directory.
    $archive = [System.IO.Compression.ZipFile]::OpenRead($BuiltApworld)
    try {
        $names = @($archive.Entries | ForEach-Object { $_.FullName.Replace([char]92, [char]47) })
        foreach ($required in @(
            'soh_extreme/__init__.py',
            'soh_extreme/Options.py',
            'soh_extreme/_vendor_oot_soh/Items.py',
            'soh_extreme/_vendor_oot_soh/Locations.py',
            'soh_extreme/_vendor_oot_soh/Regions.py',
            'soh_extreme/_vendor_oot_soh/LogicHelpers.py',
            'soh_extreme/_vendor_oot_soh/location_access/dungeons/deku_tree.py',
            'soh_extreme/_vendor_oot_soh/location_access/overworld/death_mountain_crater.py'
        )) {
            if ($names -notcontains $required) { throw "Built APWorld is missing $required" }
        }
    } finally {
        $archive.Dispose()
    }

    Write-Host '[7/7] Installing final APWorld...'
    $installDir = Split-Path -Parent $InstallPath
    New-Item -ItemType Directory -Force -Path $installDir | Out-Null
    if (Test-Path $InstallPath) {
        $backup = "$InstallPath.backup-$(Get-Date -Format yyyyMMdd-HHmmss)"
        Copy-Item -Force $InstallPath $backup
        Write-Host "Backup: $backup"
    }
    Copy-Item -Force $BuiltApworld $InstallPath

    Write-Host ''
    Write-Host 'SOH-EXTREME 0.11.9 standalone APWorld installed successfully.' -ForegroundColor Green
    Write-Host "Installed: $InstallPath"
    Write-Host "Built copy: $BuiltApworld"
    Write-Host 'Validated: no direct worlds.oot_soh dependency remains.' -ForegroundColor Green
}
finally {
    if (Test-Path $temp) { Remove-Item -Recurse -Force $temp }
}
