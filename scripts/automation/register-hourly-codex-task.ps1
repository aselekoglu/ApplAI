param(
    [string]$TaskName = "ApplAI Hourly Codex Agent",
    [string]$RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path,
    [int]$MinutesPastHour = 5
)

$ErrorActionPreference = "Stop"

$runner = Join-Path $PSScriptRoot "run-hourly-codex-agent.ps1"
$repo = (Resolve-Path $RepoRoot).Path
$now = Get-Date
$firstRun = Get-Date -Hour $now.Hour -Minute $MinutesPastHour -Second 0
if ($firstRun -le $now) {
    $firstRun = $firstRun.AddHours(1)
}

$action = New-ScheduledTaskAction `
    -Execute "powershell.exe" `
    -Argument "-NoProfile -ExecutionPolicy Bypass -File `"$runner`" -RepoRoot `"$repo`""

$trigger = New-ScheduledTaskTrigger `
    -Once `
    -At $firstRun `
    -RepetitionInterval (New-TimeSpan -Hours 1) `
    -RepetitionDuration (New-TimeSpan -Days 3650)

$settings = New-ScheduledTaskSettingsSet `
    -AllowStartIfOnBatteries `
    -DontStopIfGoingOnBatteries `
    -StartWhenAvailable `
    -MultipleInstances IgnoreNew `
    -ExecutionTimeLimit (New-TimeSpan -Minutes 59)

Register-ScheduledTask `
    -TaskName $TaskName `
    -Action $action `
    -Trigger $trigger `
    -Settings $settings `
    -Description "Runs Codex hourly in C:\Users\asele\ApplAI to inspect TODOs and safely continue implementation." `
    -Force | Out-Null

Get-ScheduledTask -TaskName $TaskName | Select-Object TaskName, State
