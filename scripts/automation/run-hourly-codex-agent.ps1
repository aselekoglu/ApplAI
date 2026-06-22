param(
    [string]$RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path,
    [int]$MaxMinutes = 55
)

$ErrorActionPreference = "Stop"

function Resolve-CodexCommand {
    $candidates = @(
        "C:\Users\asele\.local\bin\codex.cmd",
        "codex.cmd",
        "codex.exe",
        "codex"
    )

    foreach ($candidate in $candidates) {
        $command = Get-Command $candidate -ErrorAction SilentlyContinue
        if ($command) {
            return $command.Source
        }
    }

    throw "Codex CLI was not found on PATH or at C:\Users\asele\.local\bin\codex.cmd"
}

$repo = (Resolve-Path $RepoRoot).Path
$promptFile = Join-Path $PSScriptRoot "hourly-codex-prompt.md"
$logRoot = Join-Path $repo ".tmp\hourly-codex"
$lockFile = Join-Path $logRoot "run.lock.json"
$stateFile = Join-Path $logRoot "last-run.json"
$lastMessageFile = Join-Path $logRoot "last-message.md"

New-Item -ItemType Directory -Force -Path $logRoot | Out-Null

if (Test-Path $lockFile) {
    try {
        $lock = Get-Content -Raw $lockFile | ConvertFrom-Json
        $startedAt = [datetime]$lock.started_at
        $ageMinutes = ((Get-Date) - $startedAt).TotalMinutes
        if ($ageMinutes -lt ($MaxMinutes + 15)) {
            Write-Host "Another hourly Codex run appears active from $startedAt. Exiting."
            exit 0
        }
    }
    catch {
        Write-Warning "Ignoring unreadable stale lock file: $($_.Exception.Message)"
    }

    Remove-Item -LiteralPath $lockFile -Force -ErrorAction SilentlyContinue
}

$started = Get-Date
$stamp = $started.ToString("yyyyMMdd-HHmmss")
$stdoutLog = Join-Path $logRoot "$stamp.stdout.log"
$stderrLog = Join-Path $logRoot "$stamp.stderr.log"
$codexCommand = Resolve-CodexCommand

@{
    pid = $PID
    started_at = $started.ToString("o")
    repo = $repo
    codex = $codexCommand
} | ConvertTo-Json | Set-Content -Path $lockFile -Encoding UTF8

try {
    $env:GIT_CONFIG_COUNT = "1"
    $env:GIT_CONFIG_KEY_0 = "safe.directory"
    $env:GIT_CONFIG_VALUE_0 = $repo.Replace("\", "/")

    $prompt = Get-Content -Raw $promptFile
    $arguments = @(
        "exec",
        "--cd", $repo,
        "--sandbox", "workspace-write",
        "--output-last-message", $lastMessageFile,
        "-"
    )

    $processInfo = [System.Diagnostics.ProcessStartInfo]::new()
    $processInfo.FileName = $codexCommand
    foreach ($arg in $arguments) {
        [void]$processInfo.ArgumentList.Add($arg)
    }
    $processInfo.WorkingDirectory = $repo
    $processInfo.UseShellExecute = $false
    $processInfo.RedirectStandardInput = $true
    $processInfo.RedirectStandardOutput = $true
    $processInfo.RedirectStandardError = $true
    $processInfo.CreateNoWindow = $true

    $process = [System.Diagnostics.Process]::new()
    $process.StartInfo = $processInfo
    [void]$process.Start()
    $process.StandardInput.Write($prompt)
    $process.StandardInput.Close()

    $stdoutTask = $process.StandardOutput.ReadToEndAsync()
    $stderrTask = $process.StandardError.ReadToEndAsync()
    $completed = $process.WaitForExit($MaxMinutes * 60 * 1000)

    if (-not $completed) {
        $process.Kill($true)
        throw "Codex run exceeded $MaxMinutes minutes and was stopped."
    }

    $stdoutTask.Wait()
    $stderrTask.Wait()
    $stdoutTask.Result | Set-Content -Path $stdoutLog -Encoding UTF8
    $stderrTask.Result | Set-Content -Path $stderrLog -Encoding UTF8

    $finished = Get-Date
    @{
        started_at = $started.ToString("o")
        finished_at = $finished.ToString("o")
        exit_code = $process.ExitCode
        stdout_log = $stdoutLog
        stderr_log = $stderrLog
        last_message = $lastMessageFile
    } | ConvertTo-Json | Set-Content -Path $stateFile -Encoding UTF8

    exit $process.ExitCode
}
catch {
    $finished = Get-Date
    @{
        started_at = $started.ToString("o")
        finished_at = $finished.ToString("o")
        exit_code = 1
        error = $_.Exception.Message
        stdout_log = $stdoutLog
        stderr_log = $stderrLog
        last_message = $lastMessageFile
    } | ConvertTo-Json | Set-Content -Path $stateFile -Encoding UTF8
    Write-Error $_
    exit 1
}
finally {
    Remove-Item -LiteralPath $lockFile -Force -ErrorAction SilentlyContinue
}

