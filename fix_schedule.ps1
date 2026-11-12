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

# 3) daily_update: five independent triggers instead of one repeating trigger.
#    (2026-11-12) The task had ONE trigger at 15:10 with a PT2H repetition and
#    IgnoreNew. On full-scan days the 15:10 run takes ~5h and overlaps two
#    repetition points (17:10, 19:10); after that Windows drops the rest of the
#    day's repetitions - 21:10 and 23:10 never fire (log proof: 11/10 and 11/12
#    ran a single slot, 11/11 ran all). Margin data publishes at 21:00, so every
#    full-scan day the margin pages stayed one day behind until next afternoon.
#    Independent triggers do not depend on the repetition chain.
$daily = "tw_backtest_daily_update"
$days = "Monday", "Tuesday", "Wednesday", "Thursday", "Friday"
try {
    $trgs = "15:10", "17:10", "19:10", "21:10", "23:10" | ForEach-Object {
        New-ScheduledTaskTrigger -Weekly -DaysOfWeek $days -At $_
    }
    # the full pipeline needs ~5h on scan days: the 3h limit above would kill it
    $setLong = New-ScheduledTaskSettingsSet -StartWhenAvailable `
        -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -WakeToRun `
        -MultipleInstances IgnoreNew -ExecutionTimeLimit (New-TimeSpan -Hours 8)
    Set-ScheduledTask -TaskName $daily -Trigger $trgs -Settings $setLong | Out-Null
    Write-Output "$daily : 5 independent triggers (15:10/17:10/19:10/21:10/23:10), limit 8h"
} catch {
    Write-Output "$daily : trigger fix FAIL - $_"
}

# 4) evening light task: watchdog + notifications only, independent of the
#    heavy pipeline, so 21:00 margin data lands by 21:30 even if the 15:10 run
#    is still going.
$eve = "tw_backtest_evening"
try {
    $actE = New-ScheduledTaskAction -Execute "G:\Stock\tw_backtest\tw_backtest\evening_task.bat"
    $trgE = "21:25", "22:25" | ForEach-Object {
        New-ScheduledTaskTrigger -Weekly -DaysOfWeek $days -At $_
    }
    if (Get-ScheduledTask -TaskName $eve -ErrorAction SilentlyContinue) {
        Set-ScheduledTask -TaskName $eve -Action $actE -Trigger $trgE -Settings $set | Out-Null
        Write-Output "$eve : UPDATED (weekdays 21:25, 22:25)"
    } else {
        Register-ScheduledTask -TaskName $eve -Action $actE -Trigger $trgE -Settings $set | Out-Null
        Write-Output "$eve : CREATED (weekdays 21:25, 22:25)"
    }
} catch {
    Write-Output "$eve : FAIL - $_"
}

# 5) verify
Write-Output "---- verify ----"
foreach ($t in ($tasks + $eve)) {
    $task = Get-ScheduledTask -TaskName $t -ErrorAction SilentlyContinue
    if ($task) {
        $x = $task.Settings
        $at = ($task.Triggers | ForEach-Object { ([datetime]$_.StartBoundary).ToString("HH:mm") }) -join ","
        Write-Output ("{0} triggers=[{1}] StartWhenAvailable={2} Batteries={3} Wake={4} Limit={5}" -f `
            $t, $at, $x.StartWhenAvailable, (-not $x.DisallowStartIfOnBatteries), $x.WakeToRun, $x.ExecutionTimeLimit)
    }
}
