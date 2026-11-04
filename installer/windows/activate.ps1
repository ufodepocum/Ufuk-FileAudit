$root='C:\ProgramData\Ufuk-FileAudit'
$backup=Join-Path $root ('backups\'+(Get-Date -Format yyyyMMdd-HHmmss))
New-Item -ItemType Directory -Force $backup | Out-Null
if (Test-Path "$root\agent\config.json") {Copy-Item -LiteralPath "$root\agent" -Destination "$backup\agent" -Recurse}
foreach ($name in @('Ufuk-FileAudit','Ufuk-FileAudit-Envanter')) {
 if (Get-ScheduledTask -TaskName $name -ErrorAction SilentlyContinue) {
  Export-ScheduledTask $name | Set-Content (Join-Path $backup ($name+'.xml')) -Encoding Unicode
  Stop-ScheduledTask $name
 }
}
# Only processes belonging to the previous or new Ufuk-FileAudit installation.
Get-CimInstance Win32_Process | Where-Object {$_.ExecutablePath -and ($_.ExecutablePath.StartsWith($root+'\',[StringComparison]::OrdinalIgnoreCase) -or ($cfg.migrate -and $_.ExecutablePath.StartsWith('C:\ProgramData\AuditSpherePilot\',[StringComparison]::OrdinalIgnoreCase)))} | ForEach-Object {Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue}
Get-ChildItem -LiteralPath "$root\stage\agent" -File | ForEach-Object {Copy-Item -LiteralPath $_.FullName -Destination "$root\agent\" -Force}
Copy-Item -LiteralPath "$root\stage\uninstall.ps1" -Destination "$root\uninstall.ps1" -Force
$principal=New-ScheduledTaskPrincipal -UserId SYSTEM -LogonType ServiceAccount -RunLevel Highest
$settings=New-ScheduledTaskSettingsSet -MultipleInstances IgnoreNew -ExecutionTimeLimit ([TimeSpan]::Zero) -StartWhenAvailable -RestartCount 10 -RestartInterval (New-TimeSpan -Minutes 1)
foreach ($pair in @(@('Ufuk-FileAudit','launcher.py'),@('Ufuk-FileAudit-Envanter','inventory_worker.py'))) {
 $action=New-ScheduledTaskAction -Execute "$root\python\python.exe" -Argument (Join-Path "$root\agent" $pair[1]) -WorkingDirectory "$root\agent"
 $trigger=New-ScheduledTaskTrigger -AtStartup
 Register-ScheduledTask -TaskName $pair[0] -Action $action -Trigger $trigger -Principal $principal -Settings $settings -Force | Out-Null
 Start-ScheduledTask $pair[0]
}
@{product='Ufuk-FileAudit';version='1.0.0';state='active';api_url=$cfg.api_url}|ConvertTo-Json|Set-Content "$root\installation.json" -Encoding UTF8
[pscustomobject]@{state='AGENT_STARTED';backup=$backup}|ConvertTo-Json -Compress
