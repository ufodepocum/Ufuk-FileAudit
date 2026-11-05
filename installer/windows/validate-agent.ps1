$root='C:\ProgramData\Ufuk-FileAudit'
if (-not (Test-Path "$root\python\python.exe")) {throw 'AGENT_PYTHON_MISSING: Once Python ve Wireshark hazirlama adimini calistirin.'}
if (-not (Test-Path "$root\Wireshark\tshark.exe")) {throw 'TSHARK_MISSING: Python ve Wireshark hazirlama adimini tamamlayin.'}
$sig=Get-AuthenticodeSignature "$root\Wireshark\tshark.exe"
if ($sig.Status -ne 'Valid' -or $sig.SignerCertificate.Subject -notlike '*Wireshark Foundation*') {throw 'TSHARK_SIGNATURE_INVALID'}
$result=& "$root\python\python.exe" "$root\stage\agent\validate_runtime.py" "$root\stage\agent" 2>&1
if ($LASTEXITCODE -ne 0) {throw ('AGENT_RUNTIME_INVALID: '+($result | Out-String))}
$result | Out-String
