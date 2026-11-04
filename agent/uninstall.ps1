param([switch]$Purge)
$ErrorActionPreference='Stop'
$root='C:\ProgramData\Ufuk-FileAudit'
if ([IO.Path]::GetFullPath($root) -ne 'C:\ProgramData\Ufuk-FileAudit') {throw 'Unexpected uninstall path'}
foreach ($name in @('Ufuk-FileAudit','Ufuk-FileAudit-Envanter')) {
    if (Get-ScheduledTask -TaskName $name -ErrorAction SilentlyContinue) {
        Stop-ScheduledTask -TaskName $name -ErrorAction SilentlyContinue
        Unregister-ScheduledTask -TaskName $name -Confirm:$false
    }
}
Get-CimInstance Win32_Process | Where-Object {$_.ExecutablePath -and $_.ExecutablePath.StartsWith($root+'\',[StringComparison]::OrdinalIgnoreCase)} | ForEach-Object {Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue}
$uninstaller=Join-Path $root 'Wireshark\uninstall.exe'
if (Test-Path -LiteralPath $uninstaller) {Start-Process -FilePath $uninstaller -ArgumentList '/S' -WindowStyle Hidden -Wait}
Write-Output 'Ufuk-FileAudit gorevleri ve ajan islemleri kaldirildi. Dosya izinleri degistirilmedi. Ortak Npcap surucusu korundu.'
if ($Purge) {
    $resolved=(Resolve-Path -LiteralPath $root).Path
    if ($resolved -ne 'C:\ProgramData\Ufuk-FileAudit') {throw 'Unexpected resolved path'}
    Set-Location $env:TEMP
    Remove-Item -LiteralPath $resolved -Recurse -Force
} else {Write-Output 'Dosyalar korundu. Tam silme icin -Purge parametresini kullanin.'}
