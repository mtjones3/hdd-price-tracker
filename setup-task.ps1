# setup-task.ps1 — registers HDD scraper as a daily Windows Scheduled Task
# Run once from PowerShell as Administrator:
#   powershell -ExecutionPolicy Bypass -File setup-task.ps1

$TaskName   = "HDD Price Scraper"
$ScriptDir  = Split-Path -Parent $MyInvocation.MyCommand.Path
$ScriptPath = Join-Path $ScriptDir "scraper.py"
$PythonPath = (Get-Command python).Source

# Remove existing task if present
Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false -ErrorAction SilentlyContinue

$action  = New-ScheduledTaskAction `
    -Execute $PythonPath `
    -Argument "-u `"$ScriptPath`"" `
    -WorkingDirectory $ScriptDir

# Run daily at 7:30 AM
$trigger = New-ScheduledTaskTrigger -Daily -At "7:30AM"

$settings = New-ScheduledTaskSettingsSet `
    -ExecutionTimeLimit (New-TimeSpan -Hours 1) `
    -StartWhenAvailable `
    -RunOnlyIfNetworkAvailable

$env_block = New-ScheduledTaskPrincipal -UserId $env:USERNAME -LogonType Interactive

Register-ScheduledTask `
    -TaskName $TaskName `
    -Action $action `
    -Trigger $trigger `
    -Settings $settings `
    -Principal $env_block `
    -Description "Daily HDD price scraper — Seagate vs WD. Commits prices.json to GitHub, triggers Netlify redeploy." `
    -Force

Write-Host ""
Write-Host "Scheduled task '$TaskName' created." -ForegroundColor Green
Write-Host "Runs daily at 7:30 AM. Scrapes ~72 products then auto-deploys to Netlify." -ForegroundColor Cyan
Write-Host ""
Write-Host "To run manually: python scraper.py"
Write-Host "To test (no push): python scraper.py --no-push --test 5"
Write-Host "To force re-scrape today: python scraper.py --force"
