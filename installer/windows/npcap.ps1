$root='C:\ProgramData\Ufuk-FileAudit'
if (Test-Path -LiteralPath $root) {
 if (-not (Test-Path -LiteralPath "$root\installation.json")) {throw 'Hedef klasor var ama Ufuk-FileAudit kurulum isareti yok. Otomatik uzerine yazilmadi.'}
}
New-Item -ItemType Directory -Force $root,"$root\downloads","$root\agent","$root\stage\agent","$root\python","$root\logs","$root\inventory","$root\backups" | Out-Null
icacls $root /inheritance:r /grant:r '*S-1-5-18:(OI)(CI)F' '*S-1-5-32-544:(OI)(CI)F' | Out-Null
@{product='Ufuk-FileAudit';version='1.0.0';state='preparing'}|ConvertTo-Json|Set-Content "$root\installation.json" -Encoding UTF8
$service=Get-Service npcap -ErrorAction SilentlyContinue
if ($service -and $service.Status -ne 'Running') {Start-Service npcap -ErrorAction SilentlyContinue}
$service=Get-Service npcap -ErrorAction SilentlyContinue
if ($service -and $service.Status -eq 'Running' -and ((Test-Path 'C:\Windows\System32\Npcap\wpcap.dll') -or (Test-Path 'C:\Windows\System32\wpcap.dll'))) {'READY';return}
[Net.ServicePointManager]::SecurityProtocol=[Net.SecurityProtocolType]::Tls12
$ProgressPreference='SilentlyContinue'
$dest="$root\downloads\npcap-1.90.exe"
if (-not(Test-Path $dest)) {Invoke-WebRequest 'https://npcap.com/dist/npcap-1.90.exe' -OutFile $dest -UseBasicParsing}
$sig=Get-AuthenticodeSignature $dest
if ($sig.Status -ne 'Valid' -or $sig.SignerCertificate.Subject -notlike '*Nmap Software*') {throw 'Npcap imzasi dogrulanamadi.'}
'INSTALL_REQUIRED'
