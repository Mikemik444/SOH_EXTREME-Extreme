param(
    [string]$SourceRoot = 'E:\test\libultraship'
)
$ErrorActionPreference = 'Stop'
$file = Join-Path $SourceRoot 'src\fast\interpreter.cpp'
if (!(Test-Path -LiteralPath $file)) { throw "Cannot find $file" }
$text = [IO.File]::ReadAllText($file)
$backup = "$file.before-soh-extreme-tlut-fix"
if (!(Test-Path -LiteralPath $backup)) { [IO.File]::WriteAllText($backup, $text) }

# Locate GfxDpLoadTlut without assuming an exact upstream revision.
$needle = 'GfxDpLoadTlut('
$start = $text.IndexOf($needle)
if ($start -lt 0) { throw 'Could not find GfxDpLoadTlut in interpreter.cpp' }
$brace = $text.IndexOf('{', $start)
if ($brace -lt 0) { throw 'Could not find opening brace for GfxDpLoadTlut' }
$depth = 0; $end = -1
for ($i=$brace; $i -lt $text.Length; $i++) {
    if ($text[$i] -eq '{') { $depth++ }
    elseif ($text[$i] -eq '}') { $depth--; if ($depth -eq 0) { $end=$i; break } }
}
if ($end -lt 0) { throw 'Could not find end of GfxDpLoadTlut' }
$fn = $text.Substring($start, $end-$start+1)
if ($fn.Contains('SOH_EXTREME_TLUT_GUARD')) {
    Write-Host 'TLUT crash guard is already installed.'
    exit 0
}

# The crash is at the palette memcpy/read.  On Windows, validate that the entire
# source range is committed/readable before touching it.  Invalid mod/resource
# palette commands are ignored instead of crashing the renderer.
$mem = [regex]::Match($fn, 'memcpy\s*\(\s*([^,]+)\s*,\s*([^,]+)\s*,\s*([^\)]+)\)\s*;')
if (!$mem.Success) { throw 'Could not identify the TLUT memcpy in GfxDpLoadTlut; no changes made.' }
$dst = $mem.Groups[1].Value.Trim()
$src = $mem.Groups[2].Value.Trim()
$len = $mem.Groups[3].Value.Trim()

$replacement = @"
#ifdef _WIN32
        // SOH_EXTREME_TLUT_GUARD: alternate .o2r packs can contain a malformed
        // LOADTLUT source.  Fast3D used to dereference it unconditionally and
        // terminate with 0xc0000005.  Verify every page touched by this transfer.
        auto sohExtremeReadableRange = [](const void* ptr, size_t bytes) -> bool {
            if (ptr == nullptr || bytes == 0) {
                return false;
            }
            const auto begin = reinterpret_cast<uintptr_t>(ptr);
            if (begin > UINTPTR_MAX - bytes) {
                return false;
            }
            const auto finish = begin + bytes;
            auto cursor = begin;
            while (cursor < finish) {
                MEMORY_BASIC_INFORMATION mbi{};
                if (VirtualQuery(reinterpret_cast<const void*>(cursor), &mbi, sizeof(mbi)) == 0 ||
                    mbi.State != MEM_COMMIT || (mbi.Protect & (PAGE_NOACCESS | PAGE_GUARD)) != 0) {
                    return false;
                }
                const DWORD readable = PAGE_READONLY | PAGE_READWRITE | PAGE_WRITECOPY |
                                       PAGE_EXECUTE_READ | PAGE_EXECUTE_READWRITE | PAGE_EXECUTE_WRITECOPY;
                if ((mbi.Protect & readable) == 0) {
                    return false;
                }
                const auto regionEnd = reinterpret_cast<uintptr_t>(mbi.BaseAddress) + mbi.RegionSize;
                if (regionEnd <= cursor) {
                    return false;
                }
                cursor = regionEnd;
            }
            return true;
        };
        if (!sohExtremeReadableRange(reinterpret_cast<const void*>($src), static_cast<size_t>($len))) {
            SPDLOG_ERROR("SOH-EXTREME: skipped invalid LOADTLUT source {:p} ({} bytes)",
                         reinterpret_cast<const void*>($src), static_cast<size_t>($len));
            return;
        }
#endif
        memcpy($dst, $src, $len);
"@
$fn2 = $fn.Remove($mem.Index, $mem.Length).Insert($mem.Index, $replacement)
$text2 = $text.Remove($start, $fn.Length).Insert($start, $fn2)

# Add Windows API include only when needed.
if (!$text2.Contains('#include <Windows.h>') -and !$text2.Contains('#include <windows.h>')) {
    $include = "`r`n#ifdef _WIN32`r`n#include <Windows.h>`r`n#endif`r`n"
    $firstInclude = $text2.IndexOf('#include')
    if ($firstInclude -ge 0) { $text2 = $text2.Insert($firstInclude, $include) }
    else { $text2 = $include + $text2 }
}
[IO.File]::WriteAllText($file, $text2)
Write-Host "Patched $file"
Write-Host "Backup: $backup"
