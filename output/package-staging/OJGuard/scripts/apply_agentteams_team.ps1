[CmdletBinding()]
param()

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

$RepoRoot = Split-Path -Parent $PSScriptRoot
$KubeConfig = Join-Path $RepoRoot ".runtime\agentteams-kubeconfig"
$Namespace = "agentteams-system"

if (-not (Test-Path -LiteralPath $KubeConfig)) {
    throw "AgentTeams kubeconfig not found. Run scripts/setup_agentteams_k8s.ps1 first."
}

try {
    $client = New-Object System.Net.Sockets.TcpClient
    $client.Connect("127.0.0.1", 8020)
    $client.Dispose()
} catch {
    throw "OJGuard MCP is unavailable. Run scripts/start_ojguard_mcp.ps1 first."
}

& kubectl --kubeconfig $KubeConfig --namespace $Namespace apply `
    -f (Join-Path $RepoRoot "agentteams\ojguard-team.yaml")

$deadline = (Get-Date).AddMinutes(12)
do {
    Start-Sleep -Seconds 5
    $phase = & kubectl --kubeconfig $KubeConfig --namespace $Namespace `
        get team ojguard-incident-team -o 'jsonpath={.status.phase}' 2>$null
    $ready = & kubectl --kubeconfig $KubeConfig --namespace $Namespace `
        get team ojguard-incident-team -o 'jsonpath={.status.readyWorkers}' 2>$null
    $total = & kubectl --kubeconfig $KubeConfig --namespace $Namespace `
        get team ojguard-incident-team -o 'jsonpath={.status.totalWorkers}' 2>$null
    $leaderReady = & kubectl --kubeconfig $KubeConfig --namespace $Namespace `
        get team ojguard-incident-team -o 'jsonpath={.status.leaderReady}' 2>$null
    Write-Host "Team phase=$phase leader=$leaderReady workers=$ready/$total"
    if ($phase -eq "Active" -and $leaderReady -eq "true" -and
        $ready -eq $total -and [int]$total -eq 6) { break }
} while ((Get-Date) -lt $deadline)

if ($phase -ne "Active" -or $leaderReady -ne "true" -or
    $ready -ne $total -or [int]$total -ne 6) {
    & kubectl --kubeconfig $KubeConfig --namespace $Namespace get workers,teams
    throw "OJGuard AgentTeams team did not become fully ready before the deadline."
}

& (Join-Path $PSScriptRoot "verify_agentteams_security.ps1")
