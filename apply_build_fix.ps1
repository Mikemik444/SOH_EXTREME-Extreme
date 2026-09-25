$ErrorActionPreference = "Stop"
$path = Join-Path $PSScriptRoot "CMakeLists.txt"
$text = [IO.File]::ReadAllText($path)

$backup = Join-Path $PSScriptRoot "CMakeLists.txt.before_torch_fix"
if (-not (Test-Path $backup)) {
    [IO.File]::WriteAllText($backup, $text)
}

# Exclude build-time tools from the main soh recursive source glob.
$needle = 'file(GLOB_RECURSE soh__ CONFIGURE_DEPENDS RELATIVE ${CMAKE_CURRENT_SOURCE_DIR} "soh/*.c" "soh/*.cpp" "soh/*.h" "soh/*.hpp")'
$insert = @'
file(GLOB_RECURSE soh__ CONFIGURE_DEPENDS RELATIVE ${CMAKE_CURRENT_SOURCE_DIR} "soh/*.c" "soh/*.cpp" "soh/*.h" "soh/*.hpp")

# SOH-EXTREME: build-time tools have their own targets and must never be compiled into soh.exe.
list(FILTER soh__ EXCLUDE REGEX "^soh/assets/tools/")
'@

if ($text.Contains($needle)) {
    $text = $text.Replace($needle, $insert)
} elseif (-not $text.Contains('list(FILTER soh__ EXCLUDE REGEX "^soh/assets/tools/")')) {
    throw "Could not find the soh source glob to patch."
}

# Permanently use safe MSVC PDB settings on the main target.
$text = $text.Replace("`t`t`t/MP;`r`n", "`t`t`t/FS;`r`n`t`t`t/MP1;`r`n")
$text = $text.Replace("`t`t`t/MP;`n", "`t`t`t/FS;`n`t`t`t/MP1;`n")
$text = $text.Replace("            /MP;`r`n", "            /FS;`r`n            /MP1;`r`n")
$text = $text.Replace("            /MP;`n", "            /FS;`n            /MP1;`n")

[IO.File]::WriteAllText($path, $text)
Write-Host "Patched CMakeLists.txt:"
Write-Host "  - excluded soh/assets/tools from soh.exe"
Write-Host "  - changed /MP to /FS /MP1"
