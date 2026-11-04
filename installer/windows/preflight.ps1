$identity=[Security.Principal.WindowsIdentity]::GetCurrent()
$principal=[Security.Principal.WindowsPrincipal]::new($identity)
if (-not $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {throw 'Yonetici yetkili bir domain veya yerel hesap gerekli.'}
$os=Get-CimInstance Win32_OperatingSystem
if (-not [Environment]::Is64BitOperatingSystem -or [version]$os.Version -lt [version]'10.0.17763') {throw 'Windows Server 2019 veya daha yeni 64-bit sistem gerekli.'}
$shares=@(Get-SmbShare | Where-Object {-not $_.Special -and $_.Path} | Select-Object Name,Path)
$interfaces=@(Get-NetIPAddress -AddressFamily IPv4 | Where-Object {$_.IPAddress -eq $cfg.server_ip} | Select-Object InterfaceAlias,IPAddress)
$tasks=@(Get-ScheduledTask -TaskName 'Ufuk-FileAudit','Ufuk-FileAudit-Envanter' -ErrorAction SilentlyContinue | Select-Object TaskName,State)
$service=Get-Service npcap -ErrorAction SilentlyContinue
$npcap=($null -ne $service -and $service.Status -eq 'Running' -and ((Test-Path 'C:\Windows\System32\Npcap\wpcap.dll') -or (Test-Path 'C:\Windows\System32\wpcap.dll')))
[pscustomobject]@{os=$os.Caption;computer=$env:COMPUTERNAME;shares=$shares;interfaces=$interfaces;tasks=$tasks;npcap=$npcap}|ConvertTo-Json -Depth 5 -Compress
