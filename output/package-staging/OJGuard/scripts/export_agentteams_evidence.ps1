[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [datetime]$SinceUtc,
    [string]$TaskId = "OJGUARD-FINAL-20260802",
    [string]$IncidentId = "INC-67AAB2379B",
    [string]$OutputPath = "output/evidence/agentteams/agentteams-demo-result.json"
)

$ErrorActionPreference = "Stop"
$RepoRoot = Split-Path -Parent $PSScriptRoot
$KubeConfig = Join-Path $RepoRoot ".runtime\agentteams-kubeconfig"
$Namespace = "agentteams-system"
$MatrixBaseUrl = "http://127.0.0.1:18080"

function Get-SecretText([string]$Key) {
    $encoded = & kubectl --kubeconfig $KubeConfig --namespace $Namespace `
        get secret agentteams-runtime-env -o "jsonpath={.data.$Key}"
    return [Text.Encoding]::UTF8.GetString([Convert]::FromBase64String($encoded))
}

function Repair-Text([string]$Text) {
    if ($Text -notmatch "[^\u0000-\u00FF]") {
        try {
            return [Text.Encoding]::UTF8.GetString(
                [Text.Encoding]::GetEncoding(28591).GetBytes($Text)
            )
        } catch {}
    }
    return $Text
}

$login = Invoke-RestMethod -Method Post -Uri "$MatrixBaseUrl/_matrix/client/v3/login" `
    -ContentType "application/json" -Body (@{
        type = "m.login.password"
        identifier = @{ type = "m.id.user"; user = (Get-SecretText "AGENTTEAMS_ADMIN_USER") }
        password = (Get-SecretText "AGENTTEAMS_ADMIN_PASSWORD")
    } | ConvertTo-Json -Compress)
$headers = @{ Authorization = "Bearer $($login.access_token)" }

try {
    $team = & kubectl --kubeconfig $KubeConfig --namespace $Namespace `
        get team ojguard-incident-team -o json | ConvertFrom-Json
    $leader = $team.status.members | Where-Object role -eq "team_leader" | Select-Object -First 1
    $workers = @($team.status.members | Where-Object role -eq "worker")
    $sinceTimestamp = [DateTimeOffset]$SinceUtc.ToUniversalTime()
    $sinceMilliseconds = $sinceTimestamp.ToUnixTimeMilliseconds()
    $events = @()

    foreach ($member in @($leader) + $workers) {
        $encodedRoomId = [Uri]::EscapeDataString([string]$member.roomID)
        $messages = Invoke-RestMethod -Headers $headers `
            -Uri "$MatrixBaseUrl/_matrix/client/v3/rooms/$encodedRoomId/messages?dir=b&limit=100"
        $events += @($messages.chunk | Where-Object {
            $_.type -eq "m.room.message" -and
            [long]$_.origin_server_ts -ge $sinceMilliseconds -and
            $_.sender -eq $member.matrixUserID -and
            $null -ne $_.content.body
        } | ForEach-Object {
            [pscustomobject]@{
                event_id = $_.event_id
                sender = $_.sender
                member_name = $member.name
                role = $member.role
                origin_server_ts = [long]$_.origin_server_ts
                timestamp_utc = [DateTimeOffset]::FromUnixTimeMilliseconds(
                    [long]$_.origin_server_ts
                ).UtcDateTime.ToString("o")
                body = (Repair-Text ([string]$_.content.body))
            }
        })
    }

    $workerResponses = @($workers | Sort-Object name | ForEach-Object {
        $worker = $_
        $events | Where-Object {
            $_.sender -eq $worker.matrixUserID -and $_.body -match "WORKER_COMPLETE"
        } | Sort-Object { $_.body.Length } -Descending | Select-Object -First 1
    })
    $leaderFinal = $events | Where-Object {
        $_.sender -eq $leader.matrixUserID -and
        $_.body.TrimEnd().EndsWith("OJGUARD_DEMO_COMPLETE")
    } | Sort-Object origin_server_ts -Descending | Select-Object -First 1

    $completed = $workerResponses.Count -eq 6 -and $null -ne $leaderFinal
    $result = [ordered]@{
        task_id = $TaskId
        incident_id = $IncidentId
        completed = $completed
        team = "ojguard-incident-team"
        team_phase = $team.status.phase
        leader = $leader.matrixUserID
        worker_response_count = $workerResponses.Count
        started_at_utc = $sinceTimestamp.UtcDateTime.ToString("o")
        completed_at_utc = if ($leaderFinal) { $leaderFinal.timestamp_utc } else { $null }
        model = "deepseek-chat"
        budget_contract = "six worker responses plus leader report and final consolidation"
        worker_responses = $workerResponses
        leader_final = $leaderFinal
    }

    $target = Join-Path $RepoRoot $OutputPath
    New-Item -ItemType Directory -Path (Split-Path -Parent $target) -Force | Out-Null
    $result | ConvertTo-Json -Depth 10 | Set-Content -LiteralPath $target -Encoding UTF8
    $runtimeCopy = Join-Path $RepoRoot ".runtime\agentteams-demo-result.json"
    $result | ConvertTo-Json -Depth 10 | Set-Content -LiteralPath $runtimeCopy -Encoding UTF8

    if (-not $completed) {
        throw "Expected six WORKER_COMPLETE responses and a verified leader final."
    }
    Write-Host "Exported six-worker AgentTeams evidence: $target"
} finally {
    try {
        Invoke-RestMethod -Method Post -Headers $headers `
            -Uri "$MatrixBaseUrl/_matrix/client/v3/logout" -ContentType "application/json" `
            -Body "{}" | Out-Null
    } catch {}
}
