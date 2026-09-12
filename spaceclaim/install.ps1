#Requires -Version 5.1
<#
.SYNOPSIS
  Install the SpaceClaim agent preset for the DeepSeek Harness.

.DESCRIPTION
  Copies this bundle into <dshHome>\.agent-presets\<PresetId>\ and creates one
  directory junction inside it:

      <preset>\node_modules  ->  <dshHome>\profiles\node_modules

  The junction exists because the bundled Cordis plugin imports
  `@deepseek-ai/dsh-tools`, and Node resolves a module's own imports by walking
  up from the file. Without the junction the plugin cannot be loaded at all:
  Node reports ERR_MODULE_NOT_FOUND for @deepseek-ai/dsh-tools (measured), while
  the same file resolves fine from under <dshHome>\profiles.

  This file is deliberately ASCII-only: Windows PowerShell 5.1 reads a BOM-less
  .ps1 as the system ANSI codepage, and mojibake can swallow a quote and break
  parsing.

.PARAMETER DshHome
  Harness home directory. Defaults to $env:USERPROFILE\.dsh

.PARAMETER PresetId
  Preset directory name, which is also the preset id. Defaults to "spaceclaim".

.PARAMETER Force
  Replace an existing installed copy of this preset. Without it an existing
  target directory is left alone and the script fails.

.EXAMPLE
  .\install.ps1
#>
[CmdletBinding()]
param(
    [string]$DshHome = "$env:USERPROFILE\.dsh",
    [string]$PresetId = "spaceclaim",
    [switch]$Force
)

$ErrorActionPreference = 'Stop'

$source = Split-Path -Parent $MyInvocation.MyCommand.Path
$presetRoot = Join-Path $DshHome '.agent-presets'
$target = Join-Path $presetRoot $PresetId
$nodeModules = Join-Path $DshHome 'profiles\node_modules'

Write-Output "[install] source     = $source"
Write-Output "[install] dsh home   = $DshHome"
Write-Output "[install] target     = $target"

if (-not (Test-Path $nodeModules)) {
    Write-Output "[install] WARNING: $nodeModules not found."
    Write-Output "[install] The preset still installs and its skill works, but the plugin row"
    Write-Output "[install] (scdm_build) will fail to load until that directory exists."
}

if (Test-Path $target) {
    if (-not $Force) {
        throw "target already exists: $target  (pass -Force to replace it; the existing copy is deleted)"
    }
    Write-Output "[install] removing existing copy: $target"
    # Remove the junction first so the recursive delete cannot follow it into
    # the harness's node_modules.
    $existingJunction = Join-Path $target 'node_modules'
    if (Test-Path $existingJunction) {
        (Get-Item $existingJunction).Delete()
    }
    Remove-Item $target -Recurse -Force
}

New-Item -ItemType Directory -Force -Path $target | Out-Null

# Copy the bundle. .git is skipped; node_modules is created as a junction below
# rather than copied.
$exclude = @('.git', 'node_modules')
Get-ChildItem $source -Force | Where-Object { $exclude -notcontains $_.Name } | ForEach-Object {
    Copy-Item $_.FullName -Destination $target -Recurse -Force
}

if (Test-Path $nodeModules) {
    & cmd.exe /c mklink /J "$target\node_modules" "$nodeModules" | Out-Null
    if (-not (Test-Path (Join-Path $target 'node_modules'))) {
        throw "failed to create the node_modules junction at $target"
    }
    Write-Output "[install] junction created: $target\node_modules -> $nodeModules"
}

$skillCount = (Get-ChildItem (Join-Path $target 'skills') -Directory -ErrorAction SilentlyContinue | Measure-Object).Count
Write-Output "[install] skills bundled: $skillCount"
Write-Output "[install] done"
Write-Output ""
Write-Output "Next: restart DSH (or reload) and pick the preset named 'SpaceClaim'."
Write-Output "      Its sessions get the scdm_build tool plus the spaceclaim-modeling skill."
