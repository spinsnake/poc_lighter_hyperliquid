param(
    [string[]]$Symbols = @(),
    [switch]$AllShared,
    [int]$DurationSec = 0,
    [int]$FlushSec = 1,
    [int]$HyperliquidPollSec = 1,
    [int]$ParquetBatchSec = 60,
    [switch]$WriteRaw
)

$ErrorActionPreference = "Stop"

$RepoRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$PythonExe = Join-Path $RepoRoot ".venv\Scripts\python.exe"
$LogDir = Join-Path $RepoRoot "logs\collectors"
$Stamp = Get-Date -Format "yyyyMMddTHHmmssK"
$Stamp = $Stamp.Replace(":", "")

New-Item -ItemType Directory -Force -Path $LogDir | Out-Null

$StdoutLog = Join-Path $LogDir "live_collect_${Stamp}.out.log"
$StderrLog = Join-Path $LogDir "live_collect_${Stamp}.err.log"
$RunInfoPath = Join-Path $LogDir "live_collect_latest.json"

if (Test-Path $RunInfoPath) {
    try {
        $PreviousRun = Get-Content $RunInfoPath | ConvertFrom-Json
        if ($null -ne $PreviousRun.pid) {
            $PreviousProcess = Get-Process -Id $PreviousRun.pid -ErrorAction SilentlyContinue
            if ($null -ne $PreviousProcess) {
                Stop-Process -Id $PreviousRun.pid -ErrorAction Stop
                Start-Sleep -Seconds 1
            }
        }
    } catch {
    }
}

$UseAllShared = $AllShared.IsPresent -or $Symbols.Count -eq 0

$Arguments = @(
    "-u"
    "-m"
    "src.collectors.live.collect_all_live"
    "--flush-sec"
    "$FlushSec"
    "--hyperliquid-poll-sec"
    "$HyperliquidPollSec"
    "--parquet-batch-sec"
    "$ParquetBatchSec"
)

if ($UseAllShared) {
    $Arguments += "--all-shared"
} else {
    $SymbolsArg = $Symbols -join ","
    $Arguments += @("--symbols", "`"$SymbolsArg`"")
}

if ($DurationSec -gt 0) {
    $Arguments += @("--duration-sec", "$DurationSec")
}

if ($WriteRaw.IsPresent) {
    $Arguments += "--write-raw"
}

$Process = Start-Process `
    -FilePath $PythonExe `
    -ArgumentList ($Arguments -join " ") `
    -WorkingDirectory $RepoRoot `
    -RedirectStandardOutput $StdoutLog `
    -RedirectStandardError $StderrLog `
    -PassThru

$RunInfo = [ordered]@{
    started_at_local = Get-Date -Format "yyyy-MM-ddTHH:mm:ssK"
    pid = $Process.Id
    symbols = if ($UseAllShared) { @("ALL_SHARED") } else { $Symbols }
    duration_sec = $DurationSec
    flush_sec = $FlushSec
    hyperliquid_poll_sec = $HyperliquidPollSec
    parquet_batch_sec = $ParquetBatchSec
    write_raw = $WriteRaw.IsPresent
    stdout_log = $StdoutLog
    stderr_log = $StderrLog
}

$RunInfo | ConvertTo-Json -Depth 3 | Set-Content -Path $RunInfoPath -Encoding UTF8

Write-Host "Started live collector"
Write-Host "PID: $($Process.Id)"
Write-Host "Stdout: $StdoutLog"
Write-Host "Stderr: $StderrLog"
Write-Host "Run info: $RunInfoPath"
