[CmdletBinding()]
param()

$ErrorActionPreference = "Stop"
$RepoRoot = Split-Path -Parent $PSScriptRoot
$KubeConfig = Join-Path $RepoRoot ".runtime\agentteams-kubeconfig"
$encodedUser = & kubectl --kubeconfig $KubeConfig --namespace agentteams-system `
    get secret agentteams-runtime-env -o 'jsonpath={.data.AGENTTEAMS_ADMIN_USER}'
$encodedPassword = & kubectl --kubeconfig $KubeConfig --namespace agentteams-system `
    get secret agentteams-runtime-env -o 'jsonpath={.data.AGENTTEAMS_ADMIN_PASSWORD}'
$user = [Text.Encoding]::UTF8.GetString([Convert]::FromBase64String($encodedUser))
$password = [Text.Encoding]::UTF8.GetString([Convert]::FromBase64String($encodedPassword))
Write-Host "Element URL: http://127.0.0.1:18080"
Write-Host "Username: $user"
Write-Host "Password: $password"
