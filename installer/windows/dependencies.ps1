$root='C:\ProgramData\Ufuk-FileAudit'
if (-not(Test-Path "$root\installation.json")) {throw 'Once Npcap adimini tamamlayin.'}
[Net.ServicePointManager]::SecurityProtocol=[Net.SecurityProtocolType]::Tls12
$ProgressPreference='SilentlyContinue'
function Invoke-Python([string[]]$Arguments,[string]$LogFile) {
 $old=$ErrorActionPreference;$ErrorActionPreference='Continue'
 & "$root\python\python.exe" @Arguments 2>&1 | Out-File $LogFile -Encoding UTF8
 $code=$LASTEXITCODE;$ErrorActionPreference=$old
 if ($code -ne 0) {throw "Python adimi basarisiz. Log: $LogFile"}
}
if (-not(Test-Path "$root\python\python.exe")) {
 Invoke-WebRequest 'https://www.python.org/ftp/python/3.13.12/python-3.13.12-embed-amd64.zip' -OutFile "$root\downloads\python.zip" -UseBasicParsing
 Expand-Archive "$root\downloads\python.zip" "$root\python" -Force
}
$sig=Get-AuthenticodeSignature "$root\python\python.exe"
if ($sig.Status -ne 'Valid' -or $sig.SignerCertificate.Subject -notlike '*Python Software Foundation*') {throw 'Python imzasi dogrulanamadi.'}
$pth="$root\python\python313._pth"
(Get-Content $pth) -replace '#import site','import site' | Set-Content $pth -Encoding ASCII
if ((Get-Content $pth) -notcontains '..\agent') {Add-Content $pth '..\agent' -Encoding ASCII}
if (-not(Test-Path "$root\python\Lib\site-packages\pip")) {
 Invoke-WebRequest 'https://bootstrap.pypa.io/get-pip.py' -OutFile "$root\downloads\get-pip.py" -UseBasicParsing
 Invoke-Python @("$root\downloads\get-pip.py",'--no-warn-script-location') "$root\logs\pip-install.log"
}
Invoke-Python @('-m','pip','install','--disable-pip-version-check','--no-warn-script-location','-r',"$root\downloads\agent-requirements.txt") "$root\logs\dependencies.log"
if (-not(Test-Path "$root\Wireshark\tshark.exe")) {
 # Upgrades may already have Wireshark in the legacy or machine-wide directory.
 # Reuse the verified runtime without asking its installer to relocate an existing installation.
 foreach ($candidate in @('C:\ProgramData\AuditSpherePilot\Wireshark','C:\Program Files\Wireshark')) {
  $exe=Join-Path $candidate 'tshark.exe'
  if (Test-Path -LiteralPath $exe) {
   $sig=Get-AuthenticodeSignature $exe
   $version=(Get-Item -LiteralPath $exe).VersionInfo.ProductVersion
   if ($sig.Status -eq 'Valid' -and $sig.SignerCertificate.Subject -like '*Wireshark Foundation*' -and $version -like '4.6.9*') {
    New-Item -ItemType Directory -Force "$root\Wireshark" | Out-Null
    Get-ChildItem -LiteralPath $candidate -Force | Copy-Item -Destination "$root\Wireshark" -Recurse -Force
    break
   }
  }
 }
}
if (-not(Test-Path "$root\Wireshark\tshark.exe")) {
 Invoke-WebRequest 'https://2.na.dl.wireshark.org/win64/Wireshark-4.6.9-x64.exe' -OutFile "$root\downloads\wireshark.exe" -UseBasicParsing
 $sig=Get-AuthenticodeSignature "$root\downloads\wireshark.exe"
 if ($sig.Status -ne 'Valid' -or $sig.SignerCertificate.Subject -notlike '*Wireshark Foundation*') {throw 'Wireshark imzasi dogrulanamadi.'}
 $p=Start-Process "$root\downloads\wireshark.exe" -ArgumentList '/S','/desktopicon=no','/quicklaunchicon=no',"/D=$root\Wireshark" -WindowStyle Hidden -Wait -PassThru
 if ($p.ExitCode -ne 0) {throw "Wireshark kurulum kodu: $($p.ExitCode)"}
}
$sig=Get-AuthenticodeSignature "$root\Wireshark\tshark.exe"
if ($sig.Status -ne 'Valid' -or $sig.SignerCertificate.Subject -notlike '*Wireshark Foundation*') {throw 'TSHARK_SIGNATURE_INVALID'}
& "$root\Wireshark\tshark.exe" -D | Out-String
if ($LASTEXITCODE -ne 0) {throw 'TSHARK_RUNTIME_INVALID'}
'DEPENDENCIES_READY'
