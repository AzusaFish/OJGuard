[CmdletBinding()]
param(
    [int]$TimeoutMinutes = 15,
    [string]$TaskId = "OJGUARD-DEMO-001",
    [Parameter(Mandatory = $true)]
    [string]$IncidentId
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
        TimeoutSec = 20
    }
    if ($null -ne $Body) {
        $params.ContentType = "application/json"
        $params.Body = ($Body | ConvertTo-Json -Depth 12 -Compress)
    }
    return Invoke-RestMethod @params
}

function Send-MatrixMessage(
    [string]$RoomId,
    [string]$MentionMxid,
    [string]$Body,
    [string]$Token
) {
    $encodedRoomId = [Uri]::EscapeDataString($RoomId)
    $transactionId = [Uri]::EscapeDataString("ojguard-$([Guid]::NewGuid().ToString('N'))")
    $label = $MentionMxid.Split(":")[0]
    $plainBody = "$label $Body"
    $escapedBody = [Net.WebUtility]::HtmlEncode($Body).Replace("`r`n", "<br/>").Replace("`n", "<br/>")
    $content = @{
        msgtype = "m.text"
        body = $plainBody
        format = "org.matrix.custom.html"
        formatted_body = "<a href=`"https://matrix.to/#/$MentionMxid`">$label</a> $escapedBody"
        "m.mentions" = @{ user_ids = @($MentionMxid) }
    }
    $path = "/_matrix/client/v3/rooms/$encodedRoomId/send/m.room.message/$transactionId"
    return Invoke-MatrixRequest -Method "Put" -Path $path -Token $Token -Body $content
}

if (-not (Test-Path -LiteralPath $KubeConfig)) {
    throw "AgentTeams kubeconfig not found. Run scripts/setup_agentteams_k8s.ps1 first."
}

$team = & kubectl --kubeconfig $KubeConfig --namespace $Namespace `
    get team ojguard-incident-team -o json | ConvertFrom-Json
if ($team.status.phase -ne "Active" -or -not $team.status.leaderReady -or
    [int]$team.status.readyWorkers -ne 6) {
    throw "OJGuard AgentTeams team must be Active with leader ready and workers 6/6."
}

$leader = $team.status.members | Where-Object { $_.role -eq "team_leader" } | Select-Object -First 1
$workers = @($team.status.members | Where-Object { $_.role -eq "worker" })
if (-not $leader -or $workers.Count -ne 6) {
    throw "OJGuard Team Leader or six workers were not found."
}

$workerTasks = [ordered]@{
    "ojguard-signal-aggregator" = "Call incident.list_signals exactly once for incident_id=$IncidentId. Return one English message under 160 words beginning WORKER_COMPLETE role=signal. State the metric, deployment and complaint timing."
    "ojguard-root-cause-analyst" = "Call judge.replay_submission exactly once for incident_id=$IncidentId and repetitions=3. Return one English message under 160 words beginning WORKER_COMPLETE role=root_cause. State replay_mode, normal/degraded outcomes and reproducibility."
    "ojguard-impact-analyst" = "Call impact.calculate_scope exactly once for incident_id=$IncidentId. Return one English message under 160 words beginning WORKER_COMPLETE role=impact. State exact candidate, submission, score-change and advancement-change counts."
    "ojguard-remediation-planner" = "Call rejudge.create_plan exactly once for incident_id=$IncidentId. Return one English message under 160 words beginning WORKER_COMPLETE role=remediation. State control, canary and bulk gates plus stop conditions."
    "ojguard-rejudge-executor" = "Call score.calculate_changes exactly once for incident_id=$IncidentId. Return one English message under 160 words beginning WORKER_COMPLETE role=rejudge. State calculated count and that no formal score writeback is performed."
    "ojguard-verification-auditor" = "Call verification.verify_incident exactly once for incident_id=$IncidentId. Return one English message under 160 words beginning WORKER_COMPLETE role=verification. State status, coverage, duplicate, missing and cross-scope counts."
}
foreach ($name in $workerTasks.Keys) {
    if (-not ($workers | Where-Object { $_.name -eq $name })) {
        throw "Expected worker is missing from Team status: $name"
    }
}

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
        initial_device_display_name = "OJGuard bounded incident demo"
    }
    $accessToken = [string]$login.access_token
    if (-not $accessToken) { throw "Matrix login returned no access token." }

    $startTimestamp = [DateTimeOffset]::UtcNow.ToUnixTimeMilliseconds()
    $sentEvents = @()
    $leaderPrompt = @"
${TaskId}: review completed incident $IncidentId. Call report.generate_incident_report exactly once. Reply once with LEADER_REPORT_READY, stage, root cause and report evidence. Do not call specialist tools and do not emit OJGUARD_DEMO_COMPLETE yet; the runtime dispatcher will collect six independent worker checks for your final consolidation.
"@
    $sentEvents += (Send-MatrixMessage -RoomId ([string]$leader.roomID) `
        -MentionMxid ([string]$leader.matrixUserID) -Body $leaderPrompt.Trim() -Token $accessToken).event_id

    foreach ($name in $workerTasks.Keys) {
        $worker = $workers | Where-Object { $_.name -eq $name } | Select-Object -First 1
        $sentEvents += (Send-MatrixMessage -RoomId ([string]$worker.roomID) `
            -MentionMxid ([string]$worker.matrixUserID) -Body $workerTasks[$name] -Token $accessToken).event_id
    }
    Write-Host "Leader report and six bounded worker checks dispatched."

    $deadline = (Get-Date).AddMinutes($TimeoutMinutes)
    $matchingEvents = @()
    $consolidationSent = $false
    $consolidationTimestamp = [long]::MaxValue
    $finalEvent = $null
    $candidateRooms = @([string]$leader.roomID) + @($workers | ForEach-Object { [string]$_.roomID })
    $workerMxids = @($workers | ForEach-Object { [string]$_.matrixUserID })

    do {
        Start-Sleep -Seconds 8
        $matchingEvents = @()
        foreach ($candidateRoomId in $candidateRooms) {
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

        $respondingWorkers = @($matchingEvents | Where-Object {
            $workerMxids -contains $_.sender -and $_.content.body -match "WORKER_COMPLETE"
        } | Select-Object -ExpandProperty sender -Unique)

        if (-not $consolidationSent -and $respondingWorkers.Count -eq 6) {
            $digestLines = @()
            foreach ($worker in $workers | Sort-Object name) {
                $response = $matchingEvents | Where-Object {
                    $_.sender -eq $worker.matrixUserID -and $_.content.body -match "WORKER_COMPLETE"
                } | Sort-Object { $_.content.body.Length } -Descending | Select-Object -First 1
                $digestLines += "$($worker.name): $($response.content.body)"
            }
            $consolidationPrompt = @"
${TaskId}: all six independent worker checks are complete. Consolidate the evidence below without calling more tools. Reply once in English under 350 words. Include task_id=$TaskId, incident_id=$IncidentId, stage, six role conclusions, and this disclosure: Single operator switched technical/business role contexts; this is not real multi-person approval. End with the exact marker OJGUARD_DEMO_COMPLETE.

$($digestLines -join "`n")
"@
            $consolidationTimestamp = [DateTimeOffset]::UtcNow.ToUnixTimeMilliseconds()
            $sentEvents += (Send-MatrixMessage -RoomId ([string]$leader.roomID) `
                -MentionMxid ([string]$leader.matrixUserID) -Body $consolidationPrompt.Trim() -Token $accessToken).event_id
            $consolidationSent = $true
            Write-Host "Six worker checks observed; final consolidation dispatched."
        }

        if ($consolidationSent) {
            $finalEvent = $matchingEvents | Where-Object {
                $_.sender -eq $leader.matrixUserID -and
                [long]$_.origin_server_ts -ge $consolidationTimestamp -and
                $_.content.body -match "OJGUARD_DEMO_COMPLETE"
            } | Sort-Object { $_.content.body.Length } -Descending | Select-Object -First 1
        }
        Write-Host "Worker checks=$($respondingWorkers.Count)/6 final=$([bool]$finalEvent)"
        if ($finalEvent) { break }
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
    $completed = [bool]$finalEvent -and $respondingWorkers.Count -eq 6
    $result = [ordered]@{
        task_id = $TaskId
        incident_id = $IncidentId
        completed = $completed
        team = "ojguard-incident-team"
        team_phase = $team.status.phase
        leader = $leader.matrixUserID
        worker_response_count = $respondingWorkers.Count
        worker_response_mxids = $respondingWorkers
        sent_event_ids = $sentEvents
        started_at_utc = [DateTimeOffset]::FromUnixTimeMilliseconds($startTimestamp).UtcDateTime.ToString("o")
        completed_at_utc = if ($completed) { [DateTime]::UtcNow.ToString("o") } else { $null }
        llm_response_limit = 8
        events = $sanitizedEvents
    }
    $result | ConvertTo-Json -Depth 12 | Set-Content -LiteralPath $ResultFile -Encoding UTF8

    if (-not $completed) {
        throw "AgentTeams demo requires six distinct WORKER_COMPLETE replies and a post-consolidation leader marker. Evidence: $ResultFile"
    }
    Write-Host "AgentTeams demo completed with six workers. Sanitized evidence: $ResultFile"
} finally {
    if ($accessToken) {
        try {
            Invoke-MatrixRequest -Method "Post" -Path "/_matrix/client/v3/logout" -Token $accessToken -Body @{} | Out-Null
        } catch {}
    }
}
