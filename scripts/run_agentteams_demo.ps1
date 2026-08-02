[CmdletBinding()]
param(
    [int]$TimeoutMinutes = 15,
    [string]$TaskId = "OJGUARD-DEMO-001",
    [string]$ExistingRunId = ""
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

$RepoRoot = Split-Path -Parent $PSScriptRoot
$RuntimeDir = Join-Path $RepoRoot ".runtime"
$KubeConfig = Join-Path $RuntimeDir "agentteams-kubeconfig"
$Namespace = "agentteams-system"
$MatrixBaseUrl = "http://127.0.0.1:18080"
$ResultFile = Join-Path $RuntimeDir "agentteams-demo-result.json"

function Get-SecretText([string]$Key) {
    $encoded = & kubectl --kubeconfig $KubeConfig --namespace $Namespace `
        get secret agentteams-runtime-env -o "jsonpath={.data.$Key}"
    if ($LASTEXITCODE -ne 0 -or -not $encoded) {
        throw "Unable to read required AgentTeams secret key: $Key"
    }
    return [Text.Encoding]::UTF8.GetString([Convert]::FromBase64String($encoded))
}

function Invoke-MatrixRequest(
    [string]$Method,
    [string]$Path,
    [string]$Token,
    [object]$Body = $null
) {
    $headers = @{}
    if ($Token) { $headers.Authorization = "Bearer $Token" }
    $params = @{
        Method = $Method
        Uri = "$MatrixBaseUrl$Path"
        Headers = $headers
        TimeoutSec = 15
    }
    if ($null -ne $Body) {
        $params.ContentType = "application/json"
        $params.Body = ($Body | ConvertTo-Json -Depth 10 -Compress)
    }
    return Invoke-RestMethod @params
}

if (-not (Test-Path -LiteralPath $KubeConfig)) {
    throw "AgentTeams kubeconfig not found. Run scripts/setup_agentteams_k8s.ps1 first."
}

$team = & kubectl --kubeconfig $KubeConfig --namespace $Namespace `
    get team ojguard-audit-team -o json | ConvertFrom-Json
if ($team.status.phase -ne "Active" -or -not $team.status.leaderReady) {
    throw "OJGuard AgentTeams team is not fully active."
}

$leader = $team.status.members | Where-Object { $_.role -eq "team_leader" } | Select-Object -First 1
if (-not $leader) { throw "OJGuard Team Leader was not found."
}
$teamRoomId = [string]$team.status.teamRoomID
$leaderRoomId = [string]$leader.roomID
$leaderMxid = [string]$leader.matrixUserID
$encodedLeaderRoomId = [Uri]::EscapeDataString($leaderRoomId)
$accessToken = $null

try {
    $matrixReady = $false
    for ($attempt = 0; $attempt -lt 30; $attempt++) {
        Start-Sleep -Milliseconds 500
        try {
            $versions = Invoke-RestMethod -Uri "$MatrixBaseUrl/_matrix/client/versions" -TimeoutSec 2
            if ($versions.versions.Count -gt 0) { $matrixReady = $true; break }
        } catch {}
    }
    if (-not $matrixReady) {
        throw "AgentTeams gateway is unavailable. Run scripts/start_agentteams_ui.ps1 first."
    }

    $login = Invoke-MatrixRequest -Method "Post" -Path "/_matrix/client/v3/login" -Token "" -Body @{
        type = "m.login.password"
        identifier = @{ type = "m.id.user"; user = (Get-SecretText "AGENTTEAMS_ADMIN_USER") }
        password = (Get-SecretText "AGENTTEAMS_ADMIN_PASSWORD")
        initial_device_display_name = "OJGuard bounded demo"
    }
    $accessToken = [string]$login.access_token
    if (-not $accessToken) { throw "Matrix login returned no access token."
    }

    $startTimestamp = [DateTimeOffset]::UtcNow.ToUnixTimeMilliseconds()
    $taskId = $TaskId
    if ($ExistingRunId) {
        $prompt = @"
$TaskId - consolidate one bounded OJGuard contest demonstration from existing run $ExistingRunId.

Budget contract: keep responses concise. Do not browse, patch, approve, start another audit, or create another run.
1. Team Leader: call ojguard.get_run_bundle exactly once for $ExistingRunId, then delegate exactly one finding review to each named worker: specification contract; solution/overflow risk; evidence integrity; Checker bypass. Include the assigned finding and evidence ID in each delegation.
2. Each worker responds exactly once. Only the Adversarial Test Engineer calls ojguard.verify_run_evidence once; the other workers reason from the delegated record and do not call tools.
3. Team Leader consolidates once after four replies. End with the exact marker OJGUARD_DEMO_COMPLETE and include task_id=$TaskId, run_id=$ExistingRunId, four role findings with evidence IDs, gate=BLOCKED, and approval=HUMAN_ONLY.
"@
    } else {
        $prompt = @"
$TaskId - run one bounded OJGuard contest demonstration.

Budget contract: keep responses concise. Do not browse, patch, approve, or start another run.
1. Team Leader: call ojguard.audit_bundled_demo exactly once and retain its run_id.
2. Delegate exactly one concise verification to each named worker: specification contract; solution/overflow risk; replayable evidence integrity; Checker bypass. Each worker may call only ojguard.get_run_bundle and/or ojguard.verify_run_evidence and must respond once with evidence IDs.
3. Team Leader: consolidate once. End with the exact marker OJGUARD_DEMO_COMPLETE and include task_id, run_id, four role findings, gate=BLOCKED, and approval=HUMAN_ONLY.
"@
    }
    $transactionId = "ojguard-$([Guid]::NewGuid().ToString('N'))"
    $encodedTransactionId = [Uri]::EscapeDataString($transactionId)
    $leaderLabel = $leaderMxid.Split(":")[0]
    $promptBody = "$leaderLabel $($prompt.Trim())"
    $escapedPrompt = [Net.WebUtility]::HtmlEncode($prompt.Trim()).Replace("`r`n", "<br/>").Replace("`n", "<br/>")
    $content = @{
        msgtype = "m.text"
        body = $promptBody
        format = "org.matrix.custom.html"
        formatted_body = "<a href=`"https://matrix.to/#/$leaderMxid`">$leaderLabel</a> $escapedPrompt"
        "m.mentions" = @{ user_ids = @($leaderMxid) }
    }
    $sendPath = "/_matrix/client/v3/rooms/$encodedLeaderRoomId/send/m.room.message/$encodedTransactionId"
    $sent = Invoke-MatrixRequest -Method "Put" -Path $sendPath -Token $accessToken -Body $content
    Write-Host "Bounded AgentTeams demo sent. Waiting for OJGUARD_DEMO_COMPLETE..."

    $deadline = (Get-Date).AddMinutes($TimeoutMinutes)
    $matchingEvents = @()
    $nudgeSent = $false
    $nudgeEventId = $null
    $workerMxids = @($team.status.members | Where-Object { $_.role -eq "worker" } | ForEach-Object {
        [string]$_.matrixUserID
    })
    do {
        Start-Sleep -Seconds 10
        $matchingEvents = @()
        foreach ($candidateRoomId in @($leaderRoomId, $teamRoomId)) {
            $encodedCandidateRoomId = [Uri]::EscapeDataString($candidateRoomId)
            $messagesPath = "/_matrix/client/v3/rooms/$encodedCandidateRoomId/messages?dir=b&limit=100"
            $messages = Invoke-MatrixRequest -Method "Get" -Path $messagesPath -Token $accessToken
            $matchingEvents += @($messages.chunk | Where-Object {
                $_.type -eq "m.room.message" -and
                [long]$_.origin_server_ts -ge $startTimestamp -and
                $_.content.msgtype -eq "m.text"
            } | ForEach-Object {
                $_ | Add-Member -NotePropertyName "ojguard_room_id" -NotePropertyValue $candidateRoomId -PassThru
            })
        }
        $complete = $matchingEvents | Where-Object {
            $_.sender -eq $leaderMxid -and $_.content.body -match "OJGUARD_DEMO_COMPLETE"
        } | Select-Object -First 1
        $respondingWorkers = @($matchingEvents | Where-Object {
            $workerMxids -contains $_.sender
        } | Select-Object -ExpandProperty sender -Unique)
        if (-not $complete -and -not $nudgeSent -and $respondingWorkers.Count -eq $workerMxids.Count) {
            $nudgeTransactionId = [Uri]::EscapeDataString("ojguard-nudge-$([Guid]::NewGuid().ToString('N'))")
            $nudgeBody = "$leaderLabel $TaskId - all four delegated worker reviews are present (4/4). Consolidate now, reply once, and end with OJGUARD_DEMO_COMPLETE."
            $nudgeContent = @{
                msgtype = "m.text"
                body = $nudgeBody
                format = "org.matrix.custom.html"
                formatted_body = "<a href=`"https://matrix.to/#/$leaderMxid`">$leaderLabel</a> $TaskId - all four delegated worker reviews are present (4/4). Consolidate now, reply once, and end with OJGUARD_DEMO_COMPLETE."
                "m.mentions" = @{ user_ids = @($leaderMxid) }
            }
            $nudgePath = "/_matrix/client/v3/rooms/$encodedLeaderRoomId/send/m.room.message/$nudgeTransactionId"
            $nudge = Invoke-MatrixRequest -Method "Put" -Path $nudgePath -Token $accessToken -Body $nudgeContent
            $nudgeEventId = $nudge.event_id
            $nudgeSent = $true
            Write-Host "All four workers replied; final consolidation nudge sent."
        }
        Write-Host "Observed $($matchingEvents.Count) demo message(s); complete=$([bool]$complete)"
        if ($complete) { break }
    } while ((Get-Date) -lt $deadline)

    $sanitizedEvents = @($matchingEvents | Sort-Object origin_server_ts | ForEach-Object {
        [ordered]@{
            event_id = $_.event_id
            room_id = $_.ojguard_room_id
            sender = $_.sender
            timestamp_utc = [DateTimeOffset]::FromUnixTimeMilliseconds([long]$_.origin_server_ts).UtcDateTime.ToString("o")
            body = $_.content.body
        }
    })
    $result = [ordered]@{
        task_id = $taskId
        completed = [bool]$complete
        sent_event_id = $sent.event_id
        nudge_event_id = $nudgeEventId
        team = "ojguard-audit-team"
        team_phase = $team.status.phase
        leader = $leaderMxid
        leader_room_id = $leaderRoomId
        team_room_id = $teamRoomId
        started_at_utc = [DateTimeOffset]::FromUnixTimeMilliseconds($startTimestamp).UtcDateTime.ToString("o")
        completed_at_utc = if ($complete) { [DateTime]::UtcNow.ToString("o") } else { $null }
        llm_response_limit = 6
        events = $sanitizedEvents
    }
    $result | ConvertTo-Json -Depth 10 | Set-Content -LiteralPath $ResultFile -Encoding UTF8

    if (-not $complete) {
        throw "AgentTeams demo did not reach its completion marker before the deadline. Sanitized events: $ResultFile"
    }
    Write-Host "AgentTeams demo completed. Sanitized evidence: $ResultFile"
} finally {
    if ($accessToken) {
        try {
            Invoke-MatrixRequest -Method "Post" -Path "/_matrix/client/v3/logout" -Token $accessToken -Body @{} | Out-Null
        } catch {}
    }
}
