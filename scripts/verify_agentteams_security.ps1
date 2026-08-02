[CmdletBinding()]
param()

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

$RepoRoot = Split-Path -Parent $PSScriptRoot
$KubeConfig = Join-Path $RepoRoot ".runtime\agentteams-kubeconfig"
$Namespace = "agentteams-system"

if (-not (Test-Path -LiteralPath $KubeConfig)) {
    throw "AgentTeams kubeconfig not found."
}

$pods = (& kubectl --kubeconfig $KubeConfig --namespace $Namespace get pods -o json) | ConvertFrom-Json
$unsafe = @()
foreach ($pod in $pods.items) {
    foreach ($volume in @($pod.spec.volumes)) {
        if (($volume.PSObject.Properties.Name -contains "hostPath") -and
            $volume.hostPath.path -match '(docker\.sock|podman\.sock|containerd\.sock)') {
            $unsafe += "$($pod.metadata.name):$($volume.hostPath.path)"
        }
    }
}
if ($unsafe.Count -gt 0) {
    throw "Unsafe container-runtime socket mount detected: $($unsafe -join ', ')"
}

$controller = $pods.items | Where-Object { $_.metadata.labels.'app.kubernetes.io/component' -eq 'controller' } | Select-Object -First 1
if (-not $controller) { throw "AgentTeams controller pod was not found." }
$backend = $controller.spec.containers[0].env | Where-Object { $_.name -eq 'AGENTTEAMS_WORKER_BACKEND' }
if (-not $backend -or $backend.value -ne 'k8s') {
    throw "AgentTeams controller is not using the Kubernetes worker backend."
}

& kubectl --kubeconfig $KubeConfig --namespace $Namespace get pods
& kubectl --kubeconfig $KubeConfig --namespace $Namespace get managers,workers,teams
Write-Host "Security check passed: k8s backend; no Docker/Podman/containerd socket is mounted into AgentTeams pods."
