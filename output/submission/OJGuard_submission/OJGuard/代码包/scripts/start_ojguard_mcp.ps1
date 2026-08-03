[CmdletBinding()]
param()

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

$RepoRoot = Split-Path -Parent $PSScriptRoot
$RuntimeDir = Join-Path $RepoRoot ".runtime"
$PidFile = Join-Path $RuntimeDir "ojguard-mcp.pid"
$StdoutFile = Join-Path $RuntimeDir "ojguard-mcp.stdout.log"
$StderrFile = Join-Path $RuntimeDir "ojguard-mcp.stderr.log"
New-Item -ItemType Directory -Path $RuntimeDir -Force | Out-Null

if (Test-Path -LiteralPath $PidFile) {
    $existingPid = [int](Get-Content -LiteralPath $PidFile -Raw).Trim()
    if (Get-Process -Id $existingPid -ErrorAction SilentlyContinue) {
        Write-Host "OJGuard MCP is already running (PID $existingPid)."
        exit 0
    }
}

$python = Join-Path $RepoRoot ".venv\Scripts\python.exe"
if (-not (Test-Path -LiteralPath $python)) {
    $pythonCommand = Get-Command python -ErrorAction SilentlyContinue
    if (-not $pythonCommand) { throw "Python was not found." }
    $python = $pythonCommand.Source
}

# Some managed shells inject both Path and PATH. Resolve Python first, then
# remove only the redundant uppercase key before Windows builds the child env.
$pathKeys = @([Environment]::GetEnvironmentVariables().Keys | Where-Object { $_ -ceq "Path" -or $_ -ceq "PATH" })
if ($pathKeys -ccontains "Path" -and $pathKeys -ccontains "PATH") {
    [Environment]::SetEnvironmentVariable("PATH", $null, "Process")
}

$previousHost = $env:MCP_HOST
$env:MCP_HOST = "127.0.0.1"
try {
    $process = Start-Process `
        -FilePath $python `
        -ArgumentList @("-m", "mcp_server.server") `
        -WorkingDirectory $RepoRoot `
        -WindowStyle Hidden `
        -RedirectStandardOutput $StdoutFile `
        -RedirectStandardError $StderrFile `
        -PassThru
} finally {
    if ($null -eq $previousHost) { Remove-Item Env:MCP_HOST -ErrorAction SilentlyContinue }
    else { $env:MCP_HOST = $previousHost }
}
Set-Content -LiteralPath $PidFile -Value $process.Id -Encoding ASCII

$ready = $false
for ($attempt = 0; $attempt -lt 30; $attempt++) {
    Start-Sleep -Milliseconds 500
    try {
        $client = New-Object System.Net.Sockets.TcpClient
        $client.Connect("127.0.0.1", 8020)
        $client.Dispose()
        $ready = $true
        break
    } catch {}
}
if (-not $ready) {
    throw "OJGuard MCP did not become ready. See $StderrFile"
}
Write-Host "OJGuard MCP is listening on 127.0.0.1:8020 (PID $($process.Id))."
