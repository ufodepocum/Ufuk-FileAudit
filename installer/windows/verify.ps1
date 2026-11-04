$root='C:\ProgramData\Ufuk-FileAudit'
$config=Get-Content "$root\agent\config.json" -Raw -Encoding UTF8 | ConvertFrom-Json
$response=Invoke-WebRequest -Uri $config.url -Method Post -ContentType 'application/json' -Headers @{Authorization="Token $($config.token)"} -Body '[]' -UseBasicParsing -TimeoutSec 30
if ($response.StatusCode -ne 201) {throw 'Ubuntu API baglanti testi basarisiz.'}
$found=$false
for($i=0;$i -lt 15;$i++) {
 $process=Get-CimInstance Win32_Process | Where-Object {$_.Name -eq 'tshark.exe' -and $_.ExecutablePath -like "$root\*"}
 if ($process) {$found=$true;break};Start-Sleep 1
}
if (-not $found) {throw "Paket yakalama islemi baslamadi. $root\logs\agent-console.log dosyasini inceleyin."}
$service=Get-Service npcap
if ($service.Status -ne 'Running') {throw 'Npcap servisi calismiyor.'}
$tasks=@(Get-ScheduledTask 'Ufuk-FileAudit','Ufuk-FileAudit-Envanter' | Select-Object TaskName,State)
[pscustomobject]@{api_status=$response.StatusCode;npcap='Running';capture='Running';tasks=$tasks}|ConvertTo-Json -Depth 5 -Compress
