$root='C:\ProgramData\Ufuk-FileAudit'
$backup=[IO.Path]::GetFullPath([string]$cfg.backup)
if (-not $backup.StartsWith($root+'\backups\',[StringComparison]::OrdinalIgnoreCase)) {throw 'Gecersiz geri donus klasoru.'}
if (-not (Test-Path -LiteralPath (Join-Path $backup 'backup-ready'))) {'UNCHANGED';return}
foreach ($name in @('Ufuk-FileAudit','Ufuk-FileAudit-Envanter')) {
 Stop-ScheduledTask $name -ErrorAction SilentlyContinue
 Unregister-ScheduledTask $name -Confirm:$false -ErrorAction SilentlyContinue
}
Get-CimInstance Win32_Process | Where-Object {$_.ExecutablePath -and $_.ExecutablePath.StartsWith($root+'\',[StringComparison]::OrdinalIgnoreCase)} | ForEach-Object {Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue}
if (Test-Path "$backup\agent") {Get-ChildItem "$backup\agent" -File | ForEach-Object {Copy-Item -LiteralPath $_.FullName -Destination "$root\agent\" -Force}}
foreach ($name in @('Ufuk-FileAudit','Ufuk-FileAudit-Envanter')) {
 $xml=Join-Path $backup ($name+'.xml')
 if (Test-Path -LiteralPath $xml) {Register-ScheduledTask -TaskName $name -Xml (Get-Content -LiteralPath $xml -Raw) -Force | Out-Null;Start-ScheduledTask $name}
}
@{product='Ufuk-FileAudit';version='1.1.1';state='rolled_back'}|ConvertTo-Json|Set-Content "$root\installation.json" -Encoding UTF8
'ROLLBACK_COMPLETE'
