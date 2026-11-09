# fix_schedule.ps1 - make all tw_backtest scheduled tasks resilient
# Problem (2026-11-09): machine slept through 15:10/17:10/19:10 slots.
# Tasks had "No start on batteries" + no catch-up => data stale for 5+ hours.
# Fix: StartWhenAvailable (run ASAP after a missed start), allow batteries,
#      don't stop on battery, wake machine to run.
# Also registers tw_intraday_engine (weekdays 08:58) if missing.
# Run as the logged-in user:
#   powershell -NoProfile -ExecutionPolicy Bypass -File G:\Stock\tw_backtest\tw_backtest\fix_schedule.ps1

$ErrorActionPreference = "Stop"

# 1) intraday engine task (create if missing)
$eng = "tw_intraday_engine"
if (-not (Get-ScheduledTask -TaskName $eng -ErrorAction SilentlyContinue)) {
    $act = New-ScheduledTaskAction -Execute "G:\Stock\tw_backtest\tw_backtest\intraday_task.bat"
    $trg = New-ScheduledTaskTrigger -Weekly -DaysOfWeek Monday,Tuesday,Wednesday,Thursday,Friday -At 08:58
    Register-ScheduledTask -TaskName $eng -Action $act -Trigger $trg | Out-Null
    Write-Output "$eng : CREATED (weekdays 08:58)"
} else {
    Write-Output "$eng : already exists"
}

# 2) resilient settings for every task
$set = New-ScheduledTaskSettingsSet -StartWhenAvailable `
    -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -WakeToRun `
    -MultipleInstances IgnoreNew -ExecutionTimeLimit (New-TimeSpan -Hours 3)

$tasks = "tw_backtest_daily_update", "tw_backtest_morning_brief",
         "tw_backtest_weekly_review", "tw_sentinel", $eng
foreach ($t in $tasks) {
    try {
        Set-ScheduledTask -TaskName $t -Settings $set | Out-Null
        Write-Output "$t : OK (catch-up on, battery on, wake on)"
    } catch {
        Write-Output "$t : FAIL - $_"
    }
}

# 3) verify
Write-Output "---- verify ----"
foreach ($t in $tasks) {
    $x = (Get-ScheduledTask -TaskName $t -ErrorAction SilentlyContinue).Settings
    if ($x) {
        Write-Output ("{0} StartWhenAvailable={1} Batteries={2} Wake={3}" -f `
            $t, $x.StartWhenAvailable, (-not $x.DisallowStartIfOnBatteries), $x.WakeToRun)
    }
}
