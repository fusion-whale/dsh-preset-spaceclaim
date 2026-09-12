#Requires -Version 5.1
<#
.SYNOPSIS
  Run a SpaceClaim modelling script (.py) and optionally verify the result.

.DESCRIPTION
  Wraps the invocation path verified on Ansys SpaceClaim 2022 R1:

    "SpaceClaim.exe" /RunScript="<script.py>" /ScriptOutput="<log>" /Headless=True /ExitAfterScript=True

  Points that must be right or the script silently does nothing:
    * The script must be .py. A .scscript passed to /RunScript opens the GUI and never runs.
    * The switch argument must keep its quotes and go through cmd.exe; calling the exe
      directly from PowerShell strips them and the switch is ignored.
    * In /Headless mode there is no window, so script errors are visible only in the
      /ScriptOutput log.
    * SpaceClaim writes %APPDATA%\SpaceClaim (logs, journals, user.config) and reads its
      license at startup, so the caller needs a wider sandbox mode (danger-full-access).
      Under workspace-write confinement it exits silently with code 0 and runs nothing.

  The runner prepends scripts\scdm_lib.py to the modelling script, so a model script can
  call box()/name_boundaries()/finish() directly without importing anything.

  NOTE: this file is intentionally ASCII-only. Windows PowerShell 5.1 reads a BOM-less
  .ps1 as the system ANSI codepage, and mojibake can swallow a quote character and break
  parsing. Keep it ASCII, or keep a UTF-8 BOM if you ever add non-ASCII text.

.PARAMETER Script
  Path to the modelling script (.py).

.PARAMETER Out
  Expected model file (.scdocx). When given, its existence is checked.

.PARAMETER Log
  Script output log path. Defaults to <script dir>\<script name>.scdm.log.

.PARAMETER SpaceClaimExe
  Path to SpaceClaim.exe. Auto-detected when omitted (env DSH_SCDM_EXE wins).

.PARAMETER Gui
  Run with a visible UI (drop /Headless).

.PARAMETER Verify
  After a successful build, open the artifact in a fresh session and re-read its
  bounding box and named selections from disk.

.PARAMETER TimeoutSec
  Timeout in seconds, default 900.

.EXAMPLE
  .\Invoke-Scdm.ps1 -Script .\my_model.py -Out .\my_model.scdocx -Verify
#>
[CmdletBinding()]
param(
    [Parameter(Mandatory = $true, Position = 0)]
    [string]$Script,

    [string]$Out,
    [string]$Log,
    [string]$SpaceClaimExe,
    [switch]$Gui,
    [switch]$Verify,
    [int]$TimeoutSec = 900,
    [switch]$KeepTemp
)

$ErrorActionPreference = 'Stop'
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path

# ---------------------------------------------------------------- helpers

function Fail([string]$message) {
    Write-Output '[scdm] status=failed'
    Write-Output "[scdm] reason=$message"
    exit 1
}

function Find-ScdmExe([string]$explicit) {
    if ($explicit) {
        if (Test-Path $explicit) { return (Resolve-Path $explicit).Path }
        Fail "SpaceClaim.exe not found at: $explicit"
    }
    if ($env:DSH_SCDM_EXE -and (Test-Path $env:DSH_SCDM_EXE)) {
        return (Resolve-Path $env:DSH_SCDM_EXE).Path
    }
    $roots = @(
        'E:\Program Files\ANSYS Inc', 'C:\Program Files\ANSYS Inc',
        'D:\Program Files\ANSYS Inc', 'F:\Program Files\ANSYS Inc'
    )
    $found = @()
    foreach ($r in $roots) {
        if (Test-Path $r) {
            $found += Get-ChildItem $r -Directory -ErrorAction SilentlyContinue |
                ForEach-Object { Join-Path $_.FullName 'scdm\SpaceClaim.exe' } |
                Where-Object { Test-Path $_ }
        }
    }
    if (-not $found) {
        Fail 'SpaceClaim.exe not found; pass -SpaceClaimExe or set DSH_SCDM_EXE'
    }
    # the version in the folder name sorts last when newest (v221 < v231 < v241)
    return ($found | Sort-Object -Descending | Select-Object -First 1)
}

function Get-ScdmApiVersion([string]$exePath) {
    $dir = Split-Path -Parent $exePath
    # the newest API assembly may live in the root OR in its own SpaceClaim.Api.V* subfolder
    $dirs = @($dir)
    $dirs += (Get-ChildItem $dir -Directory -Filter 'SpaceClaim.Api.V*' -ErrorAction SilentlyContinue |
        ForEach-Object { $_.FullName })
    $apis = @()
    foreach ($d in $dirs) {
        $apis += Get-ChildItem $d -File -Filter 'SpaceClaim.Api.V*.dll' -ErrorAction SilentlyContinue |
            Where-Object { $_.Name -notlike '*.Scripting.dll' -and $_.Name -notlike '*.Internal.dll' } |
            ForEach-Object { ($_.Name -replace '^SpaceClaim\.Api\.(V\d+)\.dll$', '$1') }
    }
    $apis = $apis | Where-Object { $_ -match '^V\d+$' } | Sort-Object -Unique
    if ($apis) {
        return ($apis | Sort-Object { [int]($_ -replace '^V', '') } | Select-Object -Last 1)
    }
    return 'V22'
}

function Invoke-ScdmScript([string]$exe, [string]$scriptPath, [string]$logPath, [bool]$headless, [int]$timeoutSec) {
    if (Test-Path $logPath) { Remove-Item $logPath -Force -ErrorAction SilentlyContinue }
    $cmdArgs = '/c ""' + $exe + '" /RunScript="' + $scriptPath + '" /ScriptOutput="' + $logPath + '"'
    if ($headless) { $cmdArgs += ' /Headless=True' }
    $cmdArgs += ' /ExitAfterScript=True"'

    $proc = Start-Process -FilePath 'cmd.exe' -ArgumentList $cmdArgs -PassThru
    $exited = $proc.WaitForExit($timeoutSec * 1000)
    if (-not $exited) {
        & taskkill.exe /PID $proc.Id /T /F 2>&1 | Out-Null
        return @{ ExitCode = -1; TimedOut = $true }
    }
    return @{ ExitCode = $proc.ExitCode; TimedOut = $false }
}

function Show-Log([string]$logPath, [int]$tail = 60) {
    if (Test-Path $logPath) {
        $lines = Get-Content $logPath -ErrorAction SilentlyContinue
        if ($lines) {
            Write-Output '--- script output ---'
            $lines | Select-Object -Last $tail | ForEach-Object { Write-Output $_ }
            Write-Output '--- end script output ---'
        }
    }
}

# When a script fails before its first print (bad API call, import error), the
# /ScriptOutput log stays EMPTY. SpaceClaim's own application log still records
# the reason as "Script failed: <message>", so always check it on failure.
function Show-ScdmAppLog {
    $dir = Join-Path $env:APPDATA 'SpaceClaim\Log Files'
    if (-not (Test-Path $dir)) { return }
    $file = Get-ChildItem $dir -File -Filter '*.log' -ErrorAction SilentlyContinue |
        Sort-Object LastWriteTime -Descending | Select-Object -First 1
    if (-not $file) { return }
    $hits = Select-String -Path $file.FullName -Pattern 'Script failed' -ErrorAction SilentlyContinue
    if ($hits) {
        Write-Output '--- SpaceClaim application log ---'
        $hits | Select-Object -Last 3 | ForEach-Object { Write-Output ('  ' + $_.Line.Trim()) }
        Write-Output "  (source: $($file.FullName))"
        Write-Output '--- end SpaceClaim application log ---'
    }
}

# ---------------------------------------------------------------- main

$scriptPath = (Resolve-Path $Script).Path
if ([System.IO.Path]::GetExtension($scriptPath) -ne '.py') {
    Fail "the model script must be a .py file (.scscript cannot be run from the command line): $scriptPath"
}

$exe = Find-ScdmExe $SpaceClaimExe
$apiVersion = Get-ScdmApiVersion $exe

$workDir = Split-Path -Parent $scriptPath
$scriptBase = [System.IO.Path]::GetFileNameWithoutExtension($scriptPath)
if (-not $Log) { $Log = Join-Path $workDir ($scriptBase + '.scdm.log') }
$logPath = [System.IO.Path]::GetFullPath($Log)

$libPath = Join-Path $ScriptDir 'scdm_lib.py'
if (-not (Test-Path $libPath)) { Fail "helper library missing: $libPath" }

Write-Output "[scdm] exe=$exe"
Write-Output "[scdm] api=$apiVersion"
Write-Output "[scdm] script=$scriptPath"

# compose: API header + injected constants + helper library + user script
$composed = Join-Path $workDir ('_scdm_run_' + [System.Guid]::NewGuid().ToString('N').Substring(0, 8) + '.py')
$parts = @()
$parts += "# Python Script, API Version = $apiVersion"
$parts += "SCDM_API_VERSION = '" + $apiVersion + "'"
$parts += "SCDM_SCRIPT_DIR = r'" + $workDir + "'"
$parts += "SCDM_LOG_PATH = r'" + $logPath + "'"
$parts += (Get-Content $libPath -Raw -Encoding UTF8)
$parts += (Get-Content $scriptPath -Raw -Encoding UTF8)
Set-Content -Path $composed -Value ($parts -join "`r`n") -Encoding UTF8

try {
    $run = Invoke-ScdmScript -exe $exe -scriptPath $composed -logPath $logPath -headless (-not $Gui) -timeoutSec $TimeoutSec

    if ($run.TimedOut) {
        Show-Log $logPath
        Show-ScdmAppLog
        Fail "script timed out after $TimeoutSec seconds"
    }

    $logText = ''
    if (Test-Path $logPath) { $logText = Get-Content $logPath -Raw -ErrorAction SilentlyContinue }
    $ok = $logText -match '<<<SCDM_OK>>>'
    $hasTraceback = $logText -match 'Traceback \(most recent call last\)|!!! EXCEPTION !!!'

    if ($hasTraceback) {
        Show-Log $logPath
        Show-ScdmAppLog
        Fail 'the script raised an exception (see the traceback above)'
    }
    if (-not $ok) {
        Show-Log $logPath
        Show-ScdmAppLog
        Fail "no success sentinel <<<SCDM_OK>>> in the script output (end the script with finish(path)); exit code $($run.ExitCode)"
    }

    Show-Log $logPath

    if ($Out) {
        $outPath = [System.IO.Path]::GetFullPath($Out)
        if (-not (Test-Path $outPath)) {
            Fail "the script reported success but the artifact is missing: $outPath"
        }
        $item = Get-Item $outPath
        Write-Output "[scdm] artifact=$($item.FullName)"
        Write-Output ("[scdm] artifact_size={0} bytes" -f $item.Length)
    }

    if ($Verify) {
        if (-not $Out) { Fail '-Verify needs -Out so the artifact to check is known' }
        $target = [System.IO.Path]::GetFullPath($Out)
        $verifySrc = Join-Path $ScriptDir 'verify_model.py'
        if (-not (Test-Path $verifySrc)) { Fail "verification script missing: $verifySrc" }

        $verifyComposed = Join-Path $workDir ('_scdm_verify_' + [System.Guid]::NewGuid().ToString('N').Substring(0, 8) + '.py')
        $vparts = @()
        $vparts += "# Python Script, API Version = $apiVersion"
        $vparts += "SCDM_API_VERSION = '" + $apiVersion + "'"
        $vparts += "SCDM_SCRIPT_DIR = r'" + $workDir + "'"
        $vparts += "SCDM_VERIFY_TARGET = r'" + $target + "'"
        $vparts += (Get-Content $libPath -Raw -Encoding UTF8)
        $vparts += (Get-Content $verifySrc -Raw -Encoding UTF8)
        Set-Content -Path $verifyComposed -Value ($vparts -join "`r`n") -Encoding UTF8

        $verifyLog = Join-Path $workDir ($scriptBase + '.verify.log')
        try {
            $vrun = Invoke-ScdmScript -exe $exe -scriptPath $verifyComposed -logPath $verifyLog -headless (-not $Gui) -timeoutSec $TimeoutSec
            if ($vrun.TimedOut) { Fail "verification timed out after $TimeoutSec seconds" }
            $vlog = ''
            if (Test-Path $verifyLog) { $vlog = Get-Content $verifyLog -Raw -ErrorAction SilentlyContinue }
            Write-Output '--- verify (fresh session, re-read from disk) ---'
            if (Test-Path $verifyLog) { Get-Content $verifyLog | ForEach-Object { Write-Output $_ } }
            Write-Output '--- end verify ---'
            if ($vlog -notmatch '<<<SCDM_VERIFY_OK>>>') { Fail "verification did not complete; see $verifyLog" }
            Write-Output "[scdm] verify_log=$verifyLog"
        }
        finally {
            if (-not $KeepTemp -and (Test-Path $verifyComposed)) { Remove-Item $verifyComposed -Force -ErrorAction SilentlyContinue }
        }
    }

    Write-Output "[scdm] log=$logPath"
    Write-Output '[scdm] status=ok'
    exit 0
}
finally {
    if (-not $KeepTemp -and (Test-Path $composed)) { Remove-Item $composed -Force -ErrorAction SilentlyContinue }
}
