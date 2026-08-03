[CmdletBinding()]
param()

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

$RepoRoot = Split-Path -Parent $PSScriptRoot
$RuntimeDir = Join-Path $RepoRoot ".runtime"
$ToolsDir = Join-Path $RuntimeDir "tools"
$KubeConfig = Join-Path $RuntimeDir "agentteams-kubeconfig"
$SecretsFile = Join-Path $RuntimeDir "agentteams-secrets.yaml"
$ChartFile = Join-Path $RuntimeDir "agentteams-1.2.0.tgz"
$ClusterName = "ojguard-agentteams"
$Namespace = "agentteams-system"
$KindVersion = "v0.31.0"
$HelmVersion = "v3.20.2"
$KindNodeImage = "kindest/node:v1.35.0@sha256:452d707d4862f52530247495d180205e029056831160e22870e37e3f6c1ac31f"
$ChartSha256 = "f530879c26cc4e3ef8aea3e33551937604a9a803a09a358135f07a5de2de00f7"
$HelmSha256 = "24e8e5b71bab4ee17e6f989931ecf4fb144f9916cbe9990c0b6b2ec7b925c454"

New-Item -ItemType Directory -Path $RuntimeDir, $ToolsDir -Force | Out-Null

function Read-DotEnv {
    param([Parameter(Mandatory)][string]$Path)
    if (-not (Test-Path -LiteralPath $Path)) {
        throw "Missing .env file: $Path"
    }
    $values = @{}
    foreach ($line in Get-Content -LiteralPath $Path) {
        $trimmed = $line.Trim()
        if (-not $trimmed -or $trimmed.StartsWith("#")) { continue }
        $separator = $trimmed.IndexOf("=")
        if ($separator -lt 1) { continue }
        $key = $trimmed.Substring(0, $separator).Trim()
        $value = $trimmed.Substring($separator + 1).Trim()
        if (($value.StartsWith('"') -and $value.EndsWith('"')) -or
            ($value.StartsWith("'") -and $value.EndsWith("'"))) {
            $value = $value.Substring(1, $value.Length - 2)
        }
        $values[$key] = $value
    }
    return $values
}

function ConvertTo-YamlSingleQuoted {
    param([Parameter(Mandatory)][string]$Value)
    if ($Value.Contains("`r") -or $Value.Contains("`n")) {
        throw "Multiline secret values are not supported."
    }
    return "'" + $Value.Replace("'", "''") + "'"
}

function Assert-Sha256 {
    param(
        [Parameter(Mandatory)][string]$Path,
        [Parameter(Mandatory)][string]$Expected
    )
    $actual = (Get-FileHash -LiteralPath $Path -Algorithm SHA256).Hash.ToLowerInvariant()
    if ($actual -ne $Expected.ToLowerInvariant()) {
        throw "SHA-256 mismatch for $Path"
    }
}

function Get-Kind {
    $kind = Join-Path $ToolsDir "kind-$KindVersion.exe"
    if (-not (Test-Path -LiteralPath $kind)) {
        $url = "https://kind.sigs.k8s.io/dl/$KindVersion/kind-windows-amd64"
        $checksumUrl = "$url.sha256sum"
        $checksumFile = "$kind.sha256sum"
        Invoke-WebRequest -Uri $url -OutFile $kind
        Invoke-WebRequest -Uri $checksumUrl -OutFile $checksumFile
        $expected = ((Get-Content -LiteralPath $checksumFile -Raw).Trim() -split '\s+')[0]
        Assert-Sha256 -Path $kind -Expected $expected
    }
    return $kind
}

function Get-Helm {
    $helmDir = Join-Path $ToolsDir "helm-$HelmVersion"
    $helm = Join-Path $helmDir "windows-amd64\helm.exe"
    if (-not (Test-Path -LiteralPath $helm)) {
        $archive = Join-Path $ToolsDir "helm-$HelmVersion-windows-amd64.zip"
        Invoke-WebRequest -Uri "https://get.helm.sh/helm-$HelmVersion-windows-amd64.zip" -OutFile $archive
        Assert-Sha256 -Path $archive -Expected $HelmSha256
        New-Item -ItemType Directory -Path $helmDir -Force | Out-Null
        Expand-Archive -LiteralPath $archive -DestinationPath $helmDir -Force
    }
    return $helm
}

function Get-AgentTeamsChart {
    if (-not (Test-Path -LiteralPath $ChartFile)) {
        Invoke-WebRequest -Uri "https://higress.io/helm-charts/agentteams-1.2.0.tgz" -OutFile $ChartFile
    }
    Assert-Sha256 -Path $ChartFile -Expected $ChartSha256
    return $ChartFile
}

if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
    throw "Docker Desktop CLI was not found."
}
if (-not (Get-Command kubectl -ErrorAction SilentlyContinue)) {
    throw "kubectl was not found. Docker Desktop normally provides it."
}
docker info --format '{{.ServerVersion}}' | Out-Null

$envValues = Read-DotEnv -Path (Join-Path $RepoRoot ".env")
foreach ($required in @("DEEPSEEK_API_KEY", "DEEPSEEK_BASE_URL", "DEEPSEEK_MODEL")) {
    if (-not $envValues.ContainsKey($required) -or [string]::IsNullOrWhiteSpace($envValues[$required])) {
        throw "Missing required .env setting: $required"
    }
}

$secretsYaml = @(
    "credentials:"
    "  llmApiKey: $(ConvertTo-YamlSingleQuoted $envValues['DEEPSEEK_API_KEY'])"
    "  llmProvider: 'openai-compat'"
    "  llmBaseUrl: $(ConvertTo-YamlSingleQuoted $envValues['DEEPSEEK_BASE_URL'])"
    "  defaultModel: $(ConvertTo-YamlSingleQuoted $envValues['DEEPSEEK_MODEL'])"
) -join "`n"
Set-Content -LiteralPath $SecretsFile -Value $secretsYaml -Encoding UTF8

$kind = Get-Kind
$helm = Get-Helm
$chart = Get-AgentTeamsChart

$clusters = @(& $kind get clusters)
if ($clusters -notcontains $ClusterName) {
    & $kind create cluster `
        --name $ClusterName `
        --image $KindNodeImage `
        --config (Join-Path $RepoRoot "agentteams\kind-config.yaml") `
        --kubeconfig $KubeConfig `
        --wait 180s
} else {
    & $kind export kubeconfig --name $ClusterName --kubeconfig $KubeConfig
}

& $helm upgrade --install agentteams $chart `
    --kubeconfig $KubeConfig `
    --namespace $Namespace `
    --create-namespace `
    --values (Join-Path $RepoRoot "agentteams\values-kind.yaml") `
    --values $SecretsFile `
    --wait `
    --timeout 20m

# The official chart does not currently expose Manager.spec.config. Keep the
# platform Manager's autonomous heartbeat infrequent to protect small budgets.
for ($attempt = 0; $attempt -lt 60; $attempt++) {
    & kubectl --kubeconfig $KubeConfig --namespace $Namespace get manager default 2>$null | Out-Null
    if ($LASTEXITCODE -eq 0) { break }
    Start-Sleep -Seconds 2
}
& kubectl --kubeconfig $KubeConfig --namespace $Namespace apply `
    -f (Join-Path $RepoRoot "agentteams\manager-budget.yaml")

& kubectl --kubeconfig $KubeConfig --namespace $Namespace get pods
Write-Host "AgentTeams base platform is ready without a host Docker Socket mount."
Write-Host "Next: run scripts/start_ojguard_mcp.ps1, then scripts/apply_agentteams_team.ps1."
