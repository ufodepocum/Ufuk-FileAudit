$root='C:\ProgramData\Ufuk-FileAudit'
$config=Get-Content "$root\agent\config.json" -Raw -Encoding UTF8 | ConvertFrom-Json
try {$response=Invoke-WebRequest -Uri $config.url -Method Post -ContentType 'application/json' -Headers @{Authorization="Token $($config.token)"} -Body '[]' -UseBasicParsing -TimeoutSec 30}
catch {throw 'AGENT_API_UNREACHABLE'}
if ($response.StatusCode -ne 201) {throw 'Ubuntu API baglanti testi basarisiz.'}
$found=$false
for($i=0;$i -lt 15;$i++) {
 $process=Get-CimInstance Win32_Process | Where-Object {$_.Name -eq 'tshark.exe' -and $_.ExecutablePath -like "$root\*"}
 if ($process) {$found=$true;break};Start-Sleep 1
}
if (-not $found) {throw 'AGENT_CAPTURE_NOT_RUNNING'}
$service=Get-Service npcap
if ($service.Status -ne 'Running') {throw 'NPCAP_NOT_RUNNING'}
$tasks=@(Get-ScheduledTask 'Ufuk-FileAudit','Ufuk-FileAudit-Envanter' | Select-Object TaskName,State)
[pscustomobject]@{api_status=$response.StatusCode;npcap='Running';capture='Running';tasks=$tasks}|ConvertTo-Json -Depth 5 -Compress
