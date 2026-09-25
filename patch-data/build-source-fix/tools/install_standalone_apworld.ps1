[CmdletBinding()]
param([string]$ProjectRoot = '', [string]$ArchipelagoRoot = '', [switch]$SkipInstall, [switch]$CheckOnly)
$ErrorActionPreference = 'Stop'
# Compatibility entry point. Never re-vendor stock helpers over Extreme rules.
& (Join-Path $PSScriptRoot 'build_standalone_apworld.ps1') @PSBoundParameters
