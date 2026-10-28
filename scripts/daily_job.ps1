# Runs the daily job (reminders, hold expiry, GDPR clean-up) and appends the output to instance\daily-job.log.
# Windows Task Scheduler runs this every morning; see README "Daily job".
$root = Split-Path -Parent $PSScriptRoot
Set-Location $root
$log = Join-Path $root "instance\daily-job.log"
"=== $(Get-Date -Format 'yyyy-MM-dd HH:mm') ===" | Out-File -Append -Encoding utf8 $log
$ErrorActionPreference = "Continue"
& "$root\.venv\Scripts\flask.exe" send-reminders 2>&1 | ForEach-Object { "$_" } | Out-File -Append -Encoding utf8 $log
