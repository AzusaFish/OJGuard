[CmdletBinding()]
param(
    [string]$SourcePath = ".runtime/agentteams-demo-result.json",
    [string]$OutputPath = "output/evidence/agentteams/agentteams-demo-result.json"
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

$RepoRoot = Split-Path -Parent $PSScriptRoot
$source = Join-Path $RepoRoot $SourcePath
$target = Join-Path $RepoRoot $OutputPath
if (-not (Test-Path -LiteralPath $source)) {
    throw "AgentTeams runtime evidence does not exist: $source"
}

$raw = Get-Content -LiteralPath $source -Raw -Encoding utf8
$result = $raw | ConvertFrom-Json
if (-not $result.completed -or $result.orchestration_mode -ne "live_dynamic_routing" -or
    $result.posthoc_review -ne $false -or $result.initial_stage -ne "TRIAGING" -or
    $result.final_stage -ne "RESOLVED") {
    throw "Evidence is not a completed live TRIAGING-to-RESOLVED orchestration run."
}
if ([int]$result.distinct_worker_count -ne 6 -or [int]$result.worker_response_count -lt 6) {
    throw "Evidence must contain responses from all six specialist Workers."
}
if ($result.leader_final.body -notmatch "OJGUARD_DEMO_COMPLETE") {
    throw "Evidence is missing the verified final marker."
}
if ($raw -match '(?i)(access[_-]?token|api[_-]?key|password)\s*[=:]\s*["''][^"'']+') {
    throw "Evidence appears to contain a secret-like value and will not be exported."
}

New-Item -ItemType Directory -Path (Split-Path -Parent $target) -Force | Out-Null
$result | ConvertTo-Json -Depth 20 | Set-Content -LiteralPath $target -Encoding utf8
Write-Host "Exported validated live AgentTeams evidence: $target"
