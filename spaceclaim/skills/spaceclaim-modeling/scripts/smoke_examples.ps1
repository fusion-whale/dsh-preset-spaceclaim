# =====================================================================
#  smoke_examples.ps1 -- run every example model and print a result table
#
#  Usage:
#      & <skill>\scripts\smoke_examples.ps1
#      & <skill>\scripts\smoke_examples.ps1 -Only tube_bank_demo
#      & <skill>\scripts\smoke_examples.ps1 -Retries 2
#
#  Each example is built and then re-opened in a FRESH SpaceClaim session
#  (-Verify), so the numbers in the table come from disk, not from the
#  modelling script's own prints. Exit code is 0 only when every example
#  passes.
#
#  NOTE: keep this file ASCII-only -- Windows PowerShell 5.1 reads a
#  BOM-less .ps1 as the system ANSI codepage.
# =====================================================================
[CmdletBinding()]
param(
    [string[]] $Only = @(),
    [int] $Retries = 1,
    [int] $TimeoutSec = 900
)

$ErrorActionPreference = 'Continue'
$root = Split-Path -Parent $PSScriptRoot          # skill root
$runner = Join-Path $PSScriptRoot 'Invoke-Scdm.ps1'
$exDir = Join-Path $root 'examples'

if (-not (Test-Path $runner)) { Write-Error "runner not found: $runner"; exit 2 }
if (-not (Test-Path $exDir)) { Write-Error "examples not found: $exDir"; exit 2 }

$all = @('tube_bank_demo', 'pin_fin_demo', 'surface_asm_demo', 'bend90_demo', 'cht_tube_bundle_demo', 'cht_baffled_demo')
$names = if ($Only.Count -gt 0) { $Only } else { $all }

$rows = @()
$failed = 0

foreach ($name in $names) {
    $script = Join-Path $exDir ($name + '.py')
    $out = Join-Path $exDir ($name + '.scdocx')
    if (-not (Test-Path $script)) {
        Write-Host ("[smoke] MISSING {0}" -f $name) -ForegroundColor Red
        $rows += [pscustomobject]@{ Example = $name; Status = 'missing'; Bodies = '-'; Zones = '-'; Faces = '-'; Seconds = '-' }
        $failed++
        continue
    }

    $ok = $false
    $text = ''
    $secs = 0
    for ($try = 1; $try -le ($Retries + 1); $try++) {
        $sw = [Diagnostics.Stopwatch]::StartNew()
        $text = & $runner -Script $script -Out $out -Verify -TimeoutSec $TimeoutSec 2>&1 | Out-String
        $sw.Stop()
        $secs = [math]::Round($sw.Elapsed.TotalSeconds, 1)
        $ok = ($text -match 'status=ok') -and ($text -match 'SCDM_VERIFY_OK') -and ($text -notmatch 'SCDM_VERIFY_FAILED')
        if ($ok) { break }
        if ($try -le $Retries) { Write-Host ("[smoke] retry {0} (attempt {1})" -f $name, $try) -ForegroundColor Yellow }
    }

    $bodies = '-'; $zones = '-'; $faces = '-'
    $m = [regex]::Match($text, '\[verify\] bodies = (\d+)')
    if ($m.Success) { $bodies = $m.Groups[1].Value }
    $m = [regex]::Match($text, '\[verify\] named selections = (\d+)')
    if ($m.Success) { $zones = $m.Groups[1].Value }
    $m = [regex]::Match($text, '\[verify\] body\[0\] name=\S+ faces=(\d+)')
    if ($m.Success) { $faces = $m.Groups[1].Value }

    if ($ok) {
        Write-Host ("[smoke] PASS {0}  ({1}s)" -f $name, $secs) -ForegroundColor Green
    } else {
        Write-Host ("[smoke] FAIL {0}  ({1}s)" -f $name, $secs) -ForegroundColor Red
        ($text -split "`n" | Select-String -Pattern 'reason=|VERIFY EXCEPTION|Script failed' |
            Select-Object -First 3) | ForEach-Object { Write-Host ("        " + $_) }
        $failed++
    }
    $rows += [pscustomobject]@{
        Example = $name; Status = if ($ok) { 'ok' } else { 'FAILED' }
        Bodies = $bodies; Zones = $zones; Faces = $faces; Seconds = $secs
    }
}

Write-Host ''
Write-Host '=== examples smoke summary ==='
$rows | Format-Table -AutoSize | Out-String -Width 200 | Write-Host
Write-Host ("total {0}, failed {1}" -f $rows.Count, $failed)
if ($failed -gt 0) { exit 1 }
exit 0
