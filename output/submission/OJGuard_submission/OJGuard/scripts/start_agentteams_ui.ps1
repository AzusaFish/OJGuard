[CmdletBinding()]
param()

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

$RepoRoot = Split-Path -Parent $PSScriptRoot
$RuntimeDir = Join-Path $RepoRoot ".runtime"
$KubeConfig = Join-Path $RuntimeDir "agentteams-kubeconfig"
$PidFile = Join-Path $RuntimeDir "agentteams-port-forward.pid"
$StdoutFile = Join-Path $RuntimeDir "agentteams-port-forward.stdout.log"
$StderrFile = Join-Path $RuntimeDir "agentteams-port-forward.stderr.log"

if (Test-Path -LiteralPath $PidFile) {
    $existingPid = [int](Get-Content -LiteralPath $PidFile -Raw).Trim()
    if (Get-Process -Id $existingPid -ErrorAction SilentlyContinue) {
        Write-Host "AgentTeams UI forward is already running at http://127.0.0.1:18080 (PID $existingPid)."
        exit 0
    }
}

$process = Start-Process `
    -FilePath "kubectl" `
    -ArgumentList @("--kubeconfig", $KubeConfig, "--namespace", "agentteams-system", "port-forward", "service/higress-gateway", "18080:80") `
    -WorkingDirectory $RepoRoot `
    -WindowStyle Hidden `
    -RedirectStandardOutput $StdoutFile `
    -RedirectStandardError $StderrFile `
    -PassThru
Set-Content -LiteralPath $PidFile -Value $process.Id -Encoding ASCII

for ($attempt = 0; $attempt -lt 30; $attempt++) {
    Start-Sleep -Milliseconds 500
    try {
        $response = Invoke-WebRequest -Uri "http://127.0.0.1:18080" -TimeoutSec 2 -UseBasicParsing
        if ($response.StatusCode -ge 200 -and $response.StatusCode -lt 500) {
            Write-Host "AgentTeams UI: http://127.0.0.1:18080 (PID $($process.Id))"
            exit 0
        }
    } catch {}
}
throw "AgentTeams UI port-forward did not become ready. See $StderrFile"
