[CmdletBinding()]
param(
    [int]$TimeoutMinutes = 20,
    [string]$TaskId = "OJGUARD-LIVE-001",
    [string]$IncidentId = "",
    [ValidateSet("runtime_regression", "node_degradation", "checker_defect")]
    [string]$IncidentType = "runtime_regression",
    [string]$ApprovalActor = "demo-operator",
    [int]$MaxLlmResponses = 20,
    [switch]$InjectCanaryFailure,
    [switch]$AutoApprove,
    [switch]$Resume
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest
$env:PYTHONIOENCODING = "utf-8"
$env:PYTHONUTF8 = "1"

if ($InjectCanaryFailure -and $MaxLlmResponses -lt 30) {
    throw "A paid live failure-and-recovery run requires MaxLlmResponses>=30. Use deterministic recovery evidence for normal verification."
}

$RepoRoot = Split-Path -Parent $PSScriptRoot
$RuntimeDir = Join-Path $RepoRoot ".runtime"
$EnvFile = Join-Path $RepoRoot ".env"
$KubeConfig = Join-Path $RuntimeDir "agentteams-kubeconfig"
$Python = Join-Path $RepoRoot ".venv\Scripts\python.exe"
$Namespace = "agentteams-system"
$MatrixBaseUrl = "http://127.0.0.1:18080"
$ResultFile = Join-Path $RuntimeDir "agentteams-demo-result.json"
$script:AgentRunId = ""
$script:CanaryFailureInjected = $false

$realCallsEnabled = $env:LLM_REAL_CALLS_ENABLED -match '^(?i:true|1|yes)$'
if (-not $realCallsEnabled -and (Test-Path -LiteralPath $EnvFile)) {
    $realCallsEnabled = [IO.File]::ReadAllLines($EnvFile) | Where-Object {
        $_ -match '^\s*LLM_REAL_CALLS_ENABLED\s*=\s*true\s*$'
    } | Select-Object -First 1
}
if (-not $realCallsEnabled) {
    throw "Real AgentTeams model calls are disabled. Set LLM_REAL_CALLS_ENABLED=true only for an explicitly authorized paid run."
}

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
    try {
        return Invoke-RestMethod @params
    } catch {
        $details = $_.Exception.Message
        if ($_.Exception.Response -and $_.Exception.Response.GetResponseStream()) {
            $reader = New-Object IO.StreamReader($_.Exception.Response.GetResponseStream())
            $responseBody = $reader.ReadToEnd()
            if ($responseBody) { $details = "$details response=$responseBody" }
        }
        throw "Matrix $Method $Path failed: $details"
    }
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

function Invoke-RuntimeControl([string[]]$ControlArgs) {
    # Windows PowerShell promotes native stderr to an ErrorRecord. Capture the
    # complete process output before restoring Stop semantics so diagnostics are
    # not truncated to the first "Traceback" line.
    $previousErrorAction = $ErrorActionPreference
    $ErrorActionPreference = "Continue"
    try {
        $output = @(& $Python -m scripts.agentteams_runtime_control `
            --workspace-root $RepoRoot @ControlArgs 2>&1)
        $exitCode = $LASTEXITCODE
    } finally {
        $ErrorActionPreference = $previousErrorAction
    }
    if ($exitCode -ne 0) {
        throw "Runtime control failed: $($output -join "`n")"
    }
    return (($output -join "`n") | ConvertFrom-Json)
}

function Write-AgentRunEvent(
    [string]$EventId,
    [string]$EventType,
    [string]$Agent,
    [string]$Summary,
    [string]$Action = "",
    [string]$Worker = "",
    [string]$Tool = "",
    [string]$EvidenceRefs = "",
    [string]$BeforeStage = "",
    [string]$AfterStage = "",
    [string]$MetadataJson = "{}"
) {
    if (-not $script:AgentRunId) { return $null }
    $metadataBase64 = [Convert]::ToBase64String(
        [Text.Encoding]::UTF8.GetBytes($MetadataJson)
    )
    $summaryBase64 = [Convert]::ToBase64String(
        [Text.Encoding]::UTF8.GetBytes($Summary)
    )
    $eventArgs = @(
        "event", "--run-id", $script:AgentRunId,
        "--event-id", $EventId,
        "--event-type", $EventType,
        "--agent", $Agent,
        "--summary-base64", $summaryBase64,
        "--metadata-json-base64", $metadataBase64
    )
    if ($Action) { $eventArgs += @("--action", $Action) }
    if ($Worker) { $eventArgs += @("--worker", $Worker) }
    if ($Tool) { $eventArgs += @("--tool", $Tool) }
    if ($EvidenceRefs) { $eventArgs += @("--evidence-refs", $EvidenceRefs) }
    if ($BeforeStage) { $eventArgs += @("--before-stage", $BeforeStage) }
    if ($AfterStage) { $eventArgs += @("--after-stage", $AfterStage) }
    return Invoke-RuntimeControl $eventArgs
}

function Get-ApprovalValue([object]$Status, [string]$Key) {
    if ($null -eq $Status.approval_state) { return "" }
    $property = $Status.approval_state.PSObject.Properties[$Key]
    if ($null -eq $property) { return "" }
    return [string]$property.Value
}

function Wait-ApprovalGate(
    [string]$Gate,
    [string]$IncidentId,
    [DateTime]$Deadline
) {
    $requiredKeys = switch ($Gate) {
        "technical" { @("execute_plan", "run_canary_rejudge") }
        "business" { @("run_bulk_rejudge") }
        "close" { @("close_incident") }
        default { throw "Unknown approval gate: $Gate" }
    }
    do {
        $status = Invoke-RuntimeControl @("status", "--incident-id", $IncidentId)
        $values = @($requiredKeys | ForEach-Object { Get-ApprovalValue $status $_ })
        if ($values -contains "REJECTED") {
            throw "Human approval gate '$Gate' was rejected."
        }
        if (@($values | Where-Object { $_ -ne "APPROVED" }).Count -eq 0) {
            return $status
        }
        Start-Sleep -Seconds 2
    } while ((Get-Date) -lt $Deadline)
    throw "Timed out waiting for human approval gate '$Gate'."
}

function Repair-Text([string]$Text) {
    $repaired = $Text
    for ($attempt = 0; $attempt -lt 8; $attempt++) {
        if (-not $repaired -or $repaired -match "[^\u0000-\u00FF]" -or
            $repaired -notmatch "[\u00C2\u00C3\u00E2\u00E5\u00EF\u00F0]") {
            break
        }
        try {
            $repaired = [Text.Encoding]::UTF8.GetString(
                [Text.Encoding]::GetEncoding(28591).GetBytes($repaired)
            )
        } catch {
            break
        }
    }
    return $repaired
}

function Get-EventBody([object]$Event) {
    $contentProperty = $Event.PSObject.Properties["content"]
    if ($null -eq $contentProperty -or $null -eq $contentProperty.Value) { return "" }
    $bodyProperty = $contentProperty.Value.PSObject.Properties["body"]
    if ($null -eq $bodyProperty) { return "" }
    $rawBody = [string]$bodyProperty.Value
    return (Repair-Text -Text $rawBody)
}

function Wait-MemberEvent(
    [string]$RoomId,
    [string]$Sender,
    [long]$AfterTimestamp,
    [string]$Pattern,
    [DateTime]$Deadline,
    [string]$Token
) {
    $encodedRoomId = [Uri]::EscapeDataString($RoomId)
    do {
        Start-Sleep -Seconds 5
        $path = "/_matrix/client/v3/rooms/$encodedRoomId/messages?dir=b&limit=100"
        $messages = Invoke-MatrixRequest -Method "Get" -Path $path -Token $Token
        $match = $messages.chunk | Where-Object {
            $eventBody = Get-EventBody $_
            $_.type -eq "m.room.message" -and
            $_.sender -eq $Sender -and
            [long]$_.origin_server_ts -ge $AfterTimestamp -and
            $eventBody -match $Pattern
        } | Sort-Object origin_server_ts | Select-Object -Last 1
        if ($match) { return $match }
    } while ((Get-Date) -lt $Deadline)
    throw "Timed out waiting for $Sender response matching '$Pattern'."
}

if (-not (Test-Path -LiteralPath $KubeConfig)) {
    throw "AgentTeams kubeconfig not found. Run scripts/setup_agentteams_k8s.ps1 first."
}
if (-not (Test-Path -LiteralPath $Python)) {
    throw "Project Python environment not found: $Python"
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

$actions = [ordered]@{
    triage = [ordered]@{
        worker = "ojguard-signal-aggregator"
        tool = "incident.triage_signals"
        arguments = "incident_id=INCIDENT_ID"
        expected_stage = "INVESTIGATING"
        instruction = "Return the normalized signal timeline and anomaly dimensions. Do not claim a root cause."
    }
    hypothesize = [ordered]@{
        worker = "ojguard-root-cause-analyst"
        tool = "judge.replay_submission"
        arguments = "incident_id=INCIDENT_ID repetitions=3 mode=hypotheses"
        expected_stage = "INVESTIGATING"
        instruction = "Persist two falsifiable competing hypotheses. Do not execute the experiment or confirm a cause."
    }
    experiment = [ordered]@{
        worker = "ojguard-root-cause-analyst"
        tool = "judge.replay_submission"
        arguments = "incident_id=INCIDENT_ID repetitions=3 mode=experiment"
        expected_stages = @("INVESTIGATING", "IMPACT_ASSESSING")
        instruction = "Run the manager-requested node-by-image comparison and state which persisted hypothesis was confirmed or rejected."
    }
    experiment_two_dimensional = [ordered]@{
        worker = "ojguard-root-cause-analyst"
        tool = "judge.replay_submission"
        arguments = "incident_id=INCIDENT_ID repetitions=3 mode=experiment experiment_kind=cross_image_and_node_replay"
        expected_stages = @("INVESTIGATING", "IMPACT_ASSESSING")
        instruction = "Run the selected image-by-node comparison. Persist an inconclusive result instead of forcing a diagnosis."
    }
    experiment_cross_image = [ordered]@{
        worker = "ojguard-root-cause-analyst"
        tool = "judge.replay_submission"
        arguments = "incident_id=INCIDENT_ID repetitions=3 mode=experiment experiment_kind=cross_image_replay"
        expected_stages = @("INVESTIGATING", "IMPACT_ASSESSING")
        instruction = "Run the selected cross-image comparison while holding the node dimension fixed."
    }
    experiment_cross_node = [ordered]@{
        worker = "ojguard-root-cause-analyst"
        tool = "judge.replay_submission"
        arguments = "incident_id=INCIDENT_ID repetitions=3 mode=experiment experiment_kind=cross_node_replay"
        expected_stages = @("INVESTIGATING", "IMPACT_ASSESSING")
        instruction = "Run the selected cross-node comparison while holding the runtime dimension fixed."
    }
    experiment_checker_contract = [ordered]@{
        worker = "ojguard-root-cause-analyst"
        tool = "judge.replay_submission"
        arguments = "incident_id=INCIDENT_ID repetitions=3 mode=experiment experiment_kind=checker_contract_probe"
        expected_stages = @("INVESTIGATING", "IMPACT_ASSESSING")
        instruction = "Run the selected Checker contract probe and preserve any inconclusive result."
    }
    experiment_checker_adversarial = [ordered]@{
        worker = "ojguard-root-cause-analyst"
        tool = "judge.replay_submission"
        arguments = "incident_id=INCIDENT_ID repetitions=3 mode=experiment experiment_kind=checker_adversarial_probe"
        expected_stages = @("INVESTIGATING", "IMPACT_ASSESSING")
        instruction = "Run the selected adversarial Checker probe using bounded deterministic evidence."
    }
    experiment_package_contract = [ordered]@{
        worker = "ojguard-root-cause-analyst"
        tool = "judge.replay_submission"
        arguments = "incident_id=INCIDENT_ID repetitions=3 mode=experiment experiment_kind=package_contract_audit"
        expected_stages = @("INVESTIGATING", "IMPACT_ASSESSING")
        instruction = "Run the selected package contract audit; do not confirm a cause if it cannot discriminate the hypotheses."
    }
    impact = [ordered]@{
        worker = "ojguard-impact-analyst"
        tool = "impact.calculate_scope"
        arguments = "incident_id=INCIDENT_ID"
        expected_stage = "REMEDIATION_PLANNING"
        instruction = "Report candidate, submission, score-change and advancement-change counts from the frozen impact result."
    }
    plan = [ordered]@{
        worker = "ojguard-remediation-planner"
        tool = "rejudge.create_plan"
        arguments = "incident_id=INCIDENT_ID"
        expected_stage = "APPROVAL_PENDING"
        instruction = "Write the control, canary and bulk plan into IncidentContext, including stop and rollback conditions."
    }
    recovery_plan = [ordered]@{
        worker = "ojguard-remediation-planner"
        tool = "rejudge.create_plan"
        arguments = "incident_id=INCIDENT_ID mode=recovery"
        expected_stages = @("APPROVAL_PENDING")
        instruction = "Create a new recovery plan version after canary failure. Preserve the impact set, supersede the failed canary, and require fresh approval."
    }
    control_canary = [ordered]@{
        worker = "ojguard-rejudge-executor"
        tool = "rejudge.execute_batch"
        arguments = "incident_id=INCIDENT_ID phase=control_canary"
        expected_stages = @("EXECUTING", "PAUSED")
        instruction = "Execute only the approved control and canary batches. Stop on any policy or consistency failure."
    }
    bulk = [ordered]@{
        worker = "ojguard-rejudge-executor"
        tool = "rejudge.execute_batch"
        arguments = "incident_id=INCIDENT_ID phase=bulk"
        expected_stage = "REJUDGING"
        instruction = "Execute only the approved bulk batch and report the authoritative deterministic result."
    }
    verify = [ordered]@{
        worker = "ojguard-verification-auditor"
        tool = "verification.verify_incident"
        arguments = "incident_id=INCIDENT_ID"
        expected_stage = "VERIFYING"
        instruction = "Independently recompute consistency and report coverage, duplicate, missing and cross-scope counts."
    }
}

foreach ($actionName in $actions.Keys) {
    if (-not $actions[$actionName].Contains("expected_stages")) {
        $actions[$actionName]["expected_stages"] = @([string]$actions[$actionName].expected_stage)
    }
}

$actionStages = [ordered]@{
    triage = @("TRIAGING", "INVESTIGATING")
    hypothesize = @("INVESTIGATING", "INVESTIGATING")
    experiment = @("INVESTIGATING", "IMPACT_ASSESSING")
    experiment_two_dimensional = @("INVESTIGATING", "IMPACT_ASSESSING")
    experiment_cross_image = @("INVESTIGATING", "IMPACT_ASSESSING")
    experiment_cross_node = @("INVESTIGATING", "IMPACT_ASSESSING")
    experiment_checker_contract = @("INVESTIGATING", "IMPACT_ASSESSING")
    experiment_checker_adversarial = @("INVESTIGATING", "IMPACT_ASSESSING")
    experiment_package_contract = @("INVESTIGATING", "INVESTIGATING")
    impact = @("IMPACT_ASSESSING", "REMEDIATION_PLANNING")
    plan = @("REMEDIATION_PLANNING", "APPROVAL_PENDING")
    recovery_plan = @("PAUSED", "APPROVAL_PENDING")
    request_technical_approval = @("APPROVAL_PENDING", "APPROVAL_PENDING")
    control_canary = @("APPROVAL_PENDING", "EXECUTING")
    request_business_approval = @("EXECUTING", "EXECUTING")
    bulk = @("EXECUTING", "REJUDGING")
    verify = @("REJUDGING", "VERIFYING")
    request_close_approval = @("VERIFYING", "RESOLVED")
}

foreach ($actionName in $actions.Keys) {
    $workerName = [string]$actions[$actionName].worker
    if (-not ($workers | Where-Object { $_.name -eq $workerName })) {
        throw "Expected worker is missing from Team status: $workerName"
    }
}

$resumedFromStage = $null
if (-not $IncidentId) {
    $bootstrap = Invoke-RuntimeControl @(
        "bootstrap", "--incident-type", $IncidentType,
        "--task-id", $TaskId, "--max-model-responses", "$MaxLlmResponses"
    )
    $IncidentId = [string]$bootstrap.incident_id
    $script:AgentRunId = [string]$bootstrap.agent_run.run_id
    if ($bootstrap.stage -ne "TRIAGING" -or $bootstrap.precomputed_root_cause -or
        $bootstrap.precomputed_impact -or $bootstrap.precomputed_plan) {
        throw "Bootstrap must create a clean TRIAGING incident without precomputed decisions."
    }
} else {
    $existing = Invoke-RuntimeControl @(
        "ensure-run", "--incident-id", $IncidentId, "--task-id", $TaskId,
        "--max-model-responses", "$MaxLlmResponses"
    )
    $script:AgentRunId = [string]$existing.agent_run.run_id
    if ($existing.stage -ne "TRIAGING" -and -not $Resume) {
        throw "Live orchestration requires a TRIAGING incident; got $($existing.stage)."
    }
    if ($existing.stage -in @("FAILED", "ROLLED_BACK") -or
        ($existing.stage -eq "RESOLVED" -and -not $Resume)) {
        throw "Cannot resume a terminal incident at stage $($existing.stage)."
    }
    if ($Resume) { $resumedFromStage = [string]$existing.stage }
}

$startEventType = if ($Resume) { "RUN_RESUMED" } else { "RUN_STARTED" }
$startEventId = if ($Resume) { "$TaskId-RUN-RESUMED-$([Guid]::NewGuid().ToString('N'))" } else { "$TaskId-RUN-STARTED" }
Write-AgentRunEvent -EventId $startEventId -EventType $startEventType `
    -Agent "ojguard-incident-manager" -Action $(if ($Resume) { "resume" } else { "start" }) `
    -Summary $(if ($Resume) { "AgentTeams resumed from persisted IncidentContext." } else { "AgentTeams Incident Manager started dynamic incident orchestration." }) `
    -AfterStage $(if ($Resume) { $resumedFromStage } else { "TRIAGING" }) | Out-Null

$accessToken = $null
$startedAt = [DateTime]::UtcNow
$deadline = (Get-Date).AddMinutes($TimeoutMinutes)
$stageHistory = @()
$leaderDecisions = @()
$workerResponses = @()
$llmEventIds = [Collections.Generic.HashSet[string]]::new()
$previousResult = "No prior Agent result."
$recoveredFinalEvent = $null

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
        initial_device_display_name = "OJGuard live AgentTeams orchestration"
    }
    $accessToken = [string]$login.access_token
    if (-not $accessToken) { throw "Matrix login returned no access token." }

    if ($Resume -and $resumedFromStage -ne "TRIAGING") {
        $priorWorkerEvents = @{}
        foreach ($worker in $workers) {
            $encodedRoomId = [Uri]::EscapeDataString([string]$worker.roomID)
            $messages = Invoke-MatrixRequest -Method "Get" `
                -Path "/_matrix/client/v3/rooms/$encodedRoomId/messages?dir=b&limit=100" `
                -Token $accessToken
            $priorEvents = $messages.chunk | Where-Object {
                $eventBody = Get-EventBody $_
                $_.sender -eq $worker.matrixUserID -and
                $eventBody -match "WORKER_RESULT" -and
                $eventBody -match ([regex]::Escape($IncidentId))
            } | Sort-Object origin_server_ts
            foreach ($prior in $priorEvents) {
                $priorMatch = [regex]::Match(
                    (Get-EventBody $prior),
                    "WORKER_RESULT\s+action=(\S+)\s+tool=(\S+)\s+incident_id=\S+",
                    [Text.RegularExpressions.RegexOptions]::IgnoreCase
                )
                if (-not $priorMatch.Success) { continue }
                $priorAction = $priorMatch.Groups[1].Value.ToLowerInvariant()
                if (-not $actions.Contains($priorAction)) { continue }
                $priorWorkerEvents[$priorAction] = [pscustomobject]@{
                    Event = $prior
                    Worker = $worker
                    Tool = $priorMatch.Groups[2].Value
                }
            }
        }
        foreach ($priorAction in $actions.Keys) {
            if (-not $priorWorkerEvents.ContainsKey($priorAction)) { continue }
            $record = $priorWorkerEvents[$priorAction]
            $prior = $record.Event
            [void]$llmEventIds.Add([string]$prior.event_id)
            $workerResponses += [ordered]@{
                action = $priorAction
                worker = [string]$record.Worker.name
                tool = [string]$record.Tool
                event_id = [string]$prior.event_id
                body = (Get-EventBody $prior)
                timestamp_ms = [long]$prior.origin_server_ts
                recovered = $true
            }
            $stageHistory += [ordered]@{
                before_stage = [string]$actionStages[$priorAction][0]
                action = $priorAction
                worker = [string]$record.Worker.name
                tool = [string]$record.Tool
                after_stage = [string]$actionStages[$priorAction][1]
                worker_event_id = [string]$prior.event_id
                timestamp_ms = [long]$prior.origin_server_ts
                recovered_after_transport_error = $true
            }
            $previousResult = Get-EventBody $prior
        }
        # Route decisions are recovered from this run's persisted events, never
        # from the shared TeamLeader room where other incidents are present.
        $persisted = Invoke-RuntimeControl @("events", "--run-id", $script:AgentRunId)
        foreach ($priorRoute in @($persisted.events | Where-Object {
            $_.event_type -eq "ROUTE_DECISION"
        } | Sort-Object sequence)) {
            $recoveredAction = [string]$priorRoute.action
            if (-not $actionStages.Contains($recoveredAction)) { continue }
            $routeTimestamp = [DateTimeOffset]::Parse(
                [string]$priorRoute.created_at
            ).ToUnixTimeMilliseconds()
            [void]$llmEventIds.Add([string]$priorRoute.id)
            $leaderDecisions += [ordered]@{
                stage = [string]$actionStages[$recoveredAction][0]
                action = $recoveredAction
                worker = [string]$priorRoute.worker
                reason = [string]$priorRoute.summary
                evidence_refs = @($priorRoute.evidence_refs)
                event_id = [string]$priorRoute.id
                timestamp_ms = $routeTimestamp
                recovered = $true
            }
            if ($recoveredAction -like "request_*_approval") {
                $stageHistory += [ordered]@{
                    before_stage = [string]$actionStages[$recoveredAction][0]
                    action = $recoveredAction
                    actor = $ApprovalActor
                    actor_type = "human_role_context"
                    after_stage = [string]$actionStages[$recoveredAction][1]
                    leader_event_id = [string]$priorRoute.id
                    timestamp_ms = $routeTimestamp
                    recovered_from_persisted_run = $true
                }
            }
        }
        $persistedFinal = $persisted.events | Where-Object {
            $_.event_type -eq "FINAL_REPORT" -and
            ([string]$_.summary).Contains($IncidentId) -and
            ([regex]::Matches([string]$_.summary, "FINAL_REPORT").Count -eq 1) -and
            ([regex]::Matches([string]$_.summary, "OJGUARD_DEMO_COMPLETE").Count -eq 1)
        } | Sort-Object sequence | Select-Object -Last 1
        if ($persistedFinal) {
            $recoveredFinalEvent = [pscustomobject]@{
                event_id = [string]$persistedFinal.id
                origin_server_ts = [DateTimeOffset]::Parse(
                    [string]$persistedFinal.created_at
                ).ToUnixTimeMilliseconds()
                content = [pscustomobject]@{ body = [string]$persistedFinal.summary }
            }
        }
        if ($recoveredFinalEvent) {
            [void]$llmEventIds.Add([string]$recoveredFinalEvent.event_id)
        }
        $stageHistory = @($stageHistory | Sort-Object { [long]$_['timestamp_ms'] })
        $leaderDecisions = @($leaderDecisions | Sort-Object { [long]$_['timestamp_ms'] })
        $workerResponses = @($workerResponses | Sort-Object { [long]$_['timestamp_ms'] })
        if ($stageHistory.Count -gt 0) {
            $startedAt = [DateTimeOffset]::FromUnixTimeMilliseconds(
                [long]$stageHistory[0]['timestamp_ms']
            ).UtcDateTime
        }
        if ($llmEventIds.Count -gt $MaxLlmResponses) {
            throw "Recovered response count exceeds LLM budget: $($llmEventIds.Count)/$MaxLlmResponses"
        }
        Write-Host "Resumed incident $IncidentId at $resumedFromStage with $($llmEventIds.Count) recovered responses."
    }

    while ((Get-Date) -lt $deadline) {
        $before = Invoke-RuntimeControl @("status", "--incident-id", $IncidentId)
        $stage = [string]$before.stage
        if ($stage -eq "RESOLVED") { break }
        if ($stage -in @("HUMAN_REVIEW_REQUIRED", "FAILED", "ROLLED_BACK")) {
            throw "Incident entered a non-automatic terminal/hold stage: $stage"
        }
        $routeOptions = @($before.legal_route_options)
        if ($routeOptions.Count -eq 0) {
            throw "No deterministic route option exists for stage $stage."
        }
        $legalActions = @($routeOptions | ForEach-Object { [string]$_.action }) + @("human_review")
        $optionContracts = @($routeOptions | ForEach-Object {
            [ordered]@{
                action = [string]$_.action
                worker = [string]$_.worker
                experiment = if ($_.experiment_kind) { [string]$_.experiment_kind } else { "none" }
                expected_result = [string]$_.expected_result
                expected_stages = @($_.expected_stages)
                evidence_refs = @($_.evidence_refs)
                failure = [string]$_.failure_action
            }
        })
        $optionContractsJson = $optionContracts | ConvertTo-Json -Depth 8 -Compress
        $statusJson = $before | ConvertTo-Json -Depth 8 -Compress
        $previousResult = $previousResult -replace '[^\x20-\x7E]', ' '
        if ($previousResult.Length -gt 900) { $previousResult = $previousResult.Substring(0, 900) }
        $leaderPrompt = @"
$TaskId incident_id=$IncidentId. You are the Incident Manager driving a live state machine, not reviewing a completed incident.
Current status: $statusJson
Previous result: $previousResult
Legal route contracts: $optionContractsJson
Choose exactly one legal route from current evidence. When several experiments are legal, choose the one with the best expected discrimination; do not assume the host's preferred experiment. Use human_review if evidence is unsafe or inconsistent. Never call a specialist tool and never bypass an approval gate.
Reply on one line exactly: ROUTE_DECISION incident_id=$IncidentId action=<action> worker=<worker-name-or-HUMAN> experiment=<kind-or-none> failure=<human_review> evidence=<comma-separated-ids-or-none> reason=<short-reason>
"@
        $leaderSentAt = [DateTimeOffset]::UtcNow.ToUnixTimeMilliseconds()
        Send-MatrixMessage -RoomId ([string]$leader.roomID) `
            -MentionMxid ([string]$leader.matrixUserID) -Body $leaderPrompt.Trim() -Token $accessToken | Out-Null
        $leaderEvent = Wait-MemberEvent -RoomId ([string]$leader.roomID) `
            -Sender ([string]$leader.matrixUserID) -AfterTimestamp $leaderSentAt `
            -Pattern "ROUTE_DECISION\s+incident_id=$([regex]::Escape($IncidentId))" `
            -Deadline $deadline -Token $accessToken
        [void]$llmEventIds.Add([string]$leaderEvent.event_id)
        if ($llmEventIds.Count -gt $MaxLlmResponses) {
            throw "LLM response budget exceeded: $($llmEventIds.Count)/$MaxLlmResponses"
        }
        $leaderBody = [string]$leaderEvent.content.body
        $routeMatch = [regex]::Match(
            $leaderBody,
            "ROUTE_DECISION\s+incident_id=$([regex]::Escape($IncidentId))\s+action=(\S+)\s+worker=(\S+)\s+experiment=(\S+)\s+failure=(\S+)\s+evidence=(\S+)\s+reason=(.+)",
            [Text.RegularExpressions.RegexOptions]::IgnoreCase
        )
        if (-not $routeMatch.Success) { throw "Invalid TeamLeader routing response: $leaderBody" }
        $selectedAction = $routeMatch.Groups[1].Value.ToLowerInvariant()
        $selectedWorker = $routeMatch.Groups[2].Value
        $selectedExperiment = $routeMatch.Groups[3].Value
        $selectedFailure = $routeMatch.Groups[4].Value.ToLowerInvariant()
        $selectedEvidenceText = $routeMatch.Groups[5].Value
        $selectedEvidence = if ($selectedEvidenceText -eq "none") {
            @()
        } else {
            @($selectedEvidenceText.Split(",") | Where-Object { $_ })
        }
        $routeReason = $routeMatch.Groups[6].Value.Trim()
        if ($selectedAction -notin $legalActions) {
            throw "TeamLeader selected illegal action '$selectedAction' for stage $stage."
        }
        if ($selectedAction -eq "human_review") {
            if ($selectedWorker -ne "HUMAN" -or $selectedExperiment -ne "none" -or
                $selectedFailure -ne "human_review") {
                throw "The human_review route must use worker=HUMAN experiment=none failure=human_review."
            }
            $leaderDecisions += [ordered]@{
                stage = $stage; action = $selectedAction; worker = "HUMAN"; reason = $routeReason
                event_id = [string]$leaderEvent.event_id
            }
            Write-AgentRunEvent -EventId ([string]$leaderEvent.event_id) `
                -EventType "ROUTE_DECISION" -Agent "ojguard-incident-manager" `
                -Action $selectedAction -Worker "HUMAN" -Summary $routeReason `
                -BeforeStage $stage -AfterStage $stage | Out-Null
            throw "TeamLeader transferred the incident to human review: $routeReason"
        }
        $selectedOption = $routeOptions | Where-Object {
            [string]$_.action -eq $selectedAction
        } | Select-Object -First 1
        if (-not $selectedOption) {
            throw "TeamLeader selected an action without a route contract: $selectedAction"
        }
        $expectedWorker = [string]$selectedOption.worker
        if ($selectedWorker -ne $expectedWorker) {
            throw "TeamLeader routed '$selectedAction' to '$selectedWorker'; expected '$expectedWorker'."
        }
        $expectedExperiment = if ($selectedOption.experiment_kind) {
            [string]$selectedOption.experiment_kind
        } else { "none" }
        if ($selectedExperiment -ne $expectedExperiment) {
            throw "TeamLeader selected experiment '$selectedExperiment'; expected '$expectedExperiment'."
        }
        if ($selectedFailure -ne [string]$selectedOption.failure_action) {
            throw "TeamLeader selected unsupported failure action '$selectedFailure'."
        }
        $unsupportedEvidence = @($selectedEvidence | Where-Object {
            $_ -notin @($selectedOption.evidence_refs)
        })
        if ($unsupportedEvidence.Count -gt 0) {
            throw "TeamLeader cited evidence outside the route contract: $($unsupportedEvidence -join ',')."
        }
        $leaderDecisions += [ordered]@{
            stage = $stage; action = $selectedAction; worker = $selectedWorker; reason = $routeReason
            experiment_kind = if ($selectedExperiment -eq "none") { $null } else { $selectedExperiment }
            evidence_refs = $selectedEvidence
            failure_action = $selectedFailure
            event_id = [string]$leaderEvent.event_id
        }
        $routeMetadata = [ordered]@{
            experiment_kind = if ($selectedExperiment -eq "none") { $null } else { $selectedExperiment }
            expected_result = [string]$selectedOption.expected_result
            failure_action = $selectedFailure
            legal_action_count = $routeOptions.Count
        } | ConvertTo-Json -Depth 6 -Compress
        Write-AgentRunEvent -EventId ([string]$leaderEvent.event_id) `
            -EventType "ROUTE_DECISION" -Agent "ojguard-incident-manager" `
            -Action $selectedAction -Worker $selectedWorker -Summary $routeReason `
            -EvidenceRefs ($selectedEvidence -join ",") -BeforeStage $stage `
            -AfterStage $stage -MetadataJson $routeMetadata | Out-Null

        if ($selectedAction -like "request_*_approval") {
            $gate = switch ($selectedAction) {
                "request_technical_approval" { "technical" }
                "request_business_approval" { "business" }
                "request_close_approval" { "close" }
            }
            Write-AgentRunEvent -EventId "$([string]$leaderEvent.event_id)-GATE-WAIT" `
                -EventType "HUMAN_GATE" -Agent "ojguard-incident-manager" `
                -Action $selectedAction -Worker "HUMAN" `
                -Summary "Waiting for an authorized human role to approve gate=$gate." `
                -EvidenceRefs ($selectedEvidence -join ",") -BeforeStage $stage `
                -AfterStage $stage | Out-Null
            $approval = $null
            if ($AutoApprove) {
                $approval = Invoke-RuntimeControl @(
                    "approve", "--incident-id", $IncidentId,
                    "--gate", $gate, "--actor", $ApprovalActor
                )
                $after = Invoke-RuntimeControl @("status", "--incident-id", $IncidentId)
            } else {
                $after = Wait-ApprovalGate -Gate $gate -IncidentId $IncidentId -Deadline $deadline
            }
            $stageHistory += [ordered]@{
                before_stage = $stage
                action = $selectedAction
                actor = if ($AutoApprove) { $ApprovalActor } else { "external-authorized-user" }
                actor_type = "human_role_context"
                approval_gate = $gate
                after_stage = [string]$after.stage
                approval_result = $approval
                leader_event_id = [string]$leaderEvent.event_id
            }
            Write-AgentRunEvent -EventId "$([string]$leaderEvent.event_id)-GATE-APPROVED" `
                -EventType "HUMAN_GATE" -Agent "authorized-human" -Action $selectedAction `
                -Worker "HUMAN" -Summary "Authorized human approved gate=$gate." `
                -EvidenceRefs ($selectedEvidence -join ",") -BeforeStage $stage `
                -AfterStage ([string]$after.stage) | Out-Null
            $previousResult = "Human gate $gate approved; stage=$($after.stage)."
            continue
        }

        $actionSpec = $actions[$selectedAction]
        $worker = $workers | Where-Object { $_.name -eq $selectedWorker } | Select-Object -First 1
        $toolArgs = ([string]$actionSpec.arguments).Replace("INCIDENT_ID", $IncidentId)
        if ($selectedAction -eq "control_canary" -and $InjectCanaryFailure -and
            -not $script:CanaryFailureInjected) {
            $toolArgs = "$toolArgs inject_canary_failure=true"
        }
        Write-AgentRunEvent -EventId "$([string]$leaderEvent.event_id)-WORKER-STARTED" `
            -EventType "WORKER_STARTED" -Agent "ojguard-incident-manager" `
            -Action $selectedAction -Worker $selectedWorker -Tool ([string]$actionSpec.tool) `
            -Summary "Worker invocation dispatched under the selected route contract." `
            -EvidenceRefs ($selectedEvidence -join ",") -BeforeStage $stage `
            -AfterStage $stage | Out-Null
        $workerPrompt = @"
$TaskId incident_id=$IncidentId stage=$stage action=$selectedAction.
Call $($actionSpec.tool) exactly once with $toolArgs. $($actionSpec.instruction)
Begin the response exactly: WORKER_RESULT action=$selectedAction tool=$($actionSpec.tool) incident_id=$IncidentId
Then report stage_after and evidence-backed results in no more than 180 English words. Do not invent approvals or replace deterministic tool results with model judgment.
"@
        $workerSentAt = [DateTimeOffset]::UtcNow.ToUnixTimeMilliseconds()
        Send-MatrixMessage -RoomId ([string]$worker.roomID) `
            -MentionMxid ([string]$worker.matrixUserID) -Body $workerPrompt.Trim() -Token $accessToken | Out-Null
        $workerPattern = "WORKER_RESULT\s+action=$([regex]::Escape($selectedAction))"
        $workerEvent = Wait-MemberEvent -RoomId ([string]$worker.roomID) `
            -Sender ([string]$worker.matrixUserID) -AfterTimestamp $workerSentAt `
            -Pattern $workerPattern -Deadline $deadline -Token $accessToken
        [void]$llmEventIds.Add([string]$workerEvent.event_id)
        if ($llmEventIds.Count -gt $MaxLlmResponses) {
            throw "LLM response budget exceeded: $($llmEventIds.Count)/$MaxLlmResponses"
        }
        $after = Invoke-RuntimeControl @("status", "--incident-id", $IncidentId)
        $expectedStages = @($selectedOption.expected_stages | ForEach-Object { [string]$_ })
        if ([string]$after.stage -notin $expectedStages) {
            throw "Action $selectedAction left stage=$($after.stage); expected one of $($expectedStages -join ',')."
        }
        if ($selectedAction -eq "control_canary" -and [string]$after.stage -eq "PAUSED") {
            $script:CanaryFailureInjected = $true
        }
        $workerBody = [string]$workerEvent.content.body
        $workerRecord = [ordered]@{
            action = $selectedAction
            worker = $selectedWorker
            tool = [string]$actionSpec.tool
            event_id = [string]$workerEvent.event_id
            body = $workerBody
        }
        $workerResponses += $workerRecord
        $stageHistory += [ordered]@{
            before_stage = $stage
            action = $selectedAction
            worker = $selectedWorker
            tool = [string]$actionSpec.tool
            after_stage = [string]$after.stage
            leader_event_id = [string]$leaderEvent.event_id
            worker_event_id = [string]$workerEvent.event_id
        }
        Write-AgentRunEvent -EventId ([string]$workerEvent.event_id) `
            -EventType "WORKER_RESULT" -Agent $selectedWorker -Action $selectedAction `
            -Worker $selectedWorker -Tool ([string]$actionSpec.tool) `
            -Summary $workerBody -EvidenceRefs ($selectedEvidence -join ",") `
            -BeforeStage $stage -AfterStage ([string]$after.stage) | Out-Null
        Write-AgentRunEvent -EventId "$([string]$workerEvent.event_id)-STATE" `
            -EventType "STATE_TRANSITION" -Agent "ojguard-runtime-control" `
            -Action $selectedAction -Worker $selectedWorker -Tool ([string]$actionSpec.tool) `
            -Summary "Validated deterministic state transition $stage -> $($after.stage)." `
            -BeforeStage $stage -AfterStage ([string]$after.stage) | Out-Null
        if ([string]$after.stage -eq "PAUSED") {
            Write-AgentRunEvent -EventId "$([string]$workerEvent.event_id)-PAUSED" `
                -EventType "RUN_PAUSED" -Agent "ojguard-rejudge-executor" `
                -Action $selectedAction -Worker $selectedWorker `
                -Summary "Canary failure stopped execution and requires a revised plan." `
                -BeforeStage $stage -AfterStage "PAUSED" | Out-Null
        }
        if ($stage -eq "APPROVAL_PENDING" -and $selectedAction -eq "control_canary" -and
            [string]$after.stage -eq "EXECUTING" -and $script:CanaryFailureInjected) {
            Write-AgentRunEvent -EventId "$([string]$workerEvent.event_id)-RESUMED" `
                -EventType "RUN_RESUMED" -Agent "ojguard-rejudge-executor" `
                -Action $selectedAction -Worker $selectedWorker `
                -Summary "Fresh approval completed and the recovery canary passed." `
                -BeforeStage $stage -AfterStage "EXECUTING" | Out-Null
        }
        $previousResult = $workerBody
        Write-Host "$stage -> $($after.stage) via $selectedWorker"
    }

    $finalStatus = Invoke-RuntimeControl @("status", "--incident-id", $IncidentId)
    if ($finalStatus.stage -ne "RESOLVED") {
        throw "Live orchestration did not reach RESOLVED before the deadline; stage=$($finalStatus.stage)."
    }
    $distinctWorkers = @(
        $workerResponses | ForEach-Object { [string]$_['worker'] } | Select-Object -Unique
    )
    if ($distinctWorkers.Count -ne 6) {
        throw "Live orchestration requires evidence from six distinct workers; got $($distinctWorkers.Count)."
    }
    if ($recoveredFinalEvent) {
        $finalEvent = $recoveredFinalEvent
        Write-Host "Recovered the existing final report without another model call."
    } else {
        $historyJson = $stageHistory | ConvertTo-Json -Depth 10 -Compress
        $finalPrompt = @"
$TaskId incident_id=$IncidentId is RESOLVED. Call report.generate_incident_report exactly once.
Ordered execution history: $historyJson
Return exactly one compact English line under 120 words. Begin exactly: FINAL_REPORT task_id=$TaskId incident_id=$IncidentId initial_stage=TRIAGING final_stage=RESOLVED. Then summarize routing, the competing-hypothesis experiment, impact, human approvals, batches and independent verification. Include: Single operator switched technical/business role contexts; this is not real multi-person approval. End with the exact marker OJGUARD_DEMO_COMPLETE.
"@
        $finalSentAt = [DateTimeOffset]::UtcNow.ToUnixTimeMilliseconds()
        Send-MatrixMessage -RoomId ([string]$leader.roomID) `
            -MentionMxid ([string]$leader.matrixUserID) -Body $finalPrompt.Trim() -Token $accessToken | Out-Null
        $finalMarkerEvent = Wait-MemberEvent -RoomId ([string]$leader.roomID) `
            -Sender ([string]$leader.matrixUserID) -AfterTimestamp $finalSentAt `
            -Pattern "OJGUARD_DEMO_COMPLETE" -Deadline $deadline -Token $accessToken
        $encodedLeaderRoom = [Uri]::EscapeDataString([string]$leader.roomID)
        $finalMessages = Invoke-MatrixRequest -Method "Get" `
            -Path "/_matrix/client/v3/rooms/$encodedLeaderRoom/messages?dir=b&limit=100" `
            -Token $accessToken
        $finalParts = @($finalMessages.chunk | Where-Object {
            $_.sender -eq $leader.matrixUserID -and
            [long]$_.origin_server_ts -ge $finalSentAt -and
            [long]$_.origin_server_ts -le [long]$finalMarkerEvent.origin_server_ts
        } | Sort-Object origin_server_ts | ForEach-Object { Get-EventBody $_ })
        $completeFinalParts = @($finalParts | Where-Object {
            $_.Contains($IncidentId) -and $_.Contains("OJGUARD_DEMO_COMPLETE")
        })
        if ($completeFinalParts.Count -eq 0) {
            throw "Final report is not bound to the current incident_id=$IncidentId."
        }
        $finalBody = ([string]$completeFinalParts[-1]).Trim()
        if ([regex]::Matches($finalBody, "FINAL_REPORT").Count -ne 1 -or
            [regex]::Matches($finalBody, "OJGUARD_DEMO_COMPLETE").Count -ne 1) {
            throw "Final report contains duplicated streaming fragments."
        }
        $finalEvent = [pscustomobject]@{
            event_id = [string]$finalMarkerEvent.event_id
            origin_server_ts = [long]$finalMarkerEvent.origin_server_ts
            content = [pscustomobject]@{ body = $finalBody }
        }
        [void]$llmEventIds.Add([string]$finalMarkerEvent.event_id)
        if ($llmEventIds.Count -gt $MaxLlmResponses) {
            throw "LLM response budget exceeded: $($llmEventIds.Count)/$MaxLlmResponses"
        }
    }
    Write-AgentRunEvent -EventId ([string]$finalEvent.event_id) `
        -EventType "FINAL_REPORT" -Agent "ojguard-incident-manager" `
        -Action "final_report" -Worker "ojguard-incident-manager" `
        -Tool "report.generate_incident_report" `
        -Summary (Get-EventBody $finalEvent) -BeforeStage "RESOLVED" `
        -AfterStage "RESOLVED" | Out-Null

    $result = [ordered]@{
        task_id = $TaskId
        incident_id = $IncidentId
        agent_run_id = $script:AgentRunId
        completed = $true
        orchestration_mode = "live_dynamic_routing"
        posthoc_review = $false
        initial_stage = "TRIAGING"
        resumed_from_stage = $resumedFromStage
        final_stage = "RESOLVED"
        team = "ojguard-incident-team"
        team_phase = [string]$team.status.phase
        leader = [string]$leader.matrixUserID
        distinct_worker_count = $distinctWorkers.Count
        distinct_workers = $distinctWorkers
        worker_response_count = $workerResponses.Count
        leader_decision_count = $leaderDecisions.Count
        llm_response_count = $llmEventIds.Count
        max_llm_responses = $MaxLlmResponses
        model = "deepseek-chat"
        budget_contract = "At most 20 responses in one live run; deterministic tools remain authoritative."
        started_at_utc = $startedAt.ToString("o")
        completed_at_utc = [DateTime]::UtcNow.ToString("o")
        stage_history = $stageHistory
        leader_decisions = $leaderDecisions
        worker_responses = $workerResponses
        leader_final = [ordered]@{
            event_id = [string]$finalEvent.event_id
            body = (Get-EventBody $finalEvent)
        }
    }
    $result | ConvertTo-Json -Depth 20 | Set-Content -LiteralPath $ResultFile -Encoding UTF8
    Write-Host "Live AgentTeams orchestration completed. Sanitized evidence: $ResultFile"
} catch {
    if ($script:AgentRunId) {
        try {
            Write-AgentRunEvent -EventId "$TaskId-ERROR-$([Guid]::NewGuid().ToString('N'))" `
                -EventType "ERROR" -Agent "ojguard-runtime-control" -Action "orchestration_error" `
                -Summary $_.Exception.Message | Out-Null
        } catch {}
    }
    throw
} finally {
    if ($accessToken) {
        try {
            Invoke-MatrixRequest -Method "Post" -Path "/_matrix/client/v3/logout" `
                -Token $accessToken -Body @{} | Out-Null
        } catch {}
    }
}
