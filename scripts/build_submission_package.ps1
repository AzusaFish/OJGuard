$ErrorActionPreference = "Stop"

$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$outputRoot = Join-Path $repoRoot "output"
$stagingBase = Join-Path $outputRoot "package-staging"
$stagingRoot = Join-Path $stagingBase "OJGuard"
$zipPath = Join-Path $outputRoot "submission\OJGuard_submission.zip"

if (-not $stagingRoot.StartsWith($stagingBase, [StringComparison]::OrdinalIgnoreCase)) {
    throw "Unsafe staging path: $stagingRoot"
}
if (-not $zipPath.StartsWith($outputRoot, [StringComparison]::OrdinalIgnoreCase)) {
    throw "Unsafe ZIP path: $zipPath"
}

if (Test-Path -LiteralPath $stagingBase) {
    Remove-Item -LiteralPath $stagingBase -Recurse -Force
}
New-Item -ItemType Directory -Path $stagingRoot -Force | Out-Null

$allowedRoots = @(
    "backend", "frontend", "runner", "mcp_server", "agents", "agentteams",
    "skills", "demo", "scripts", "tests", "materials"
)
$rootFiles = @(
    ".dockerignore", ".env.example", ".gitattributes", ".gitignore",
    "LICENSE", "pyproject.toml", "uv.lock"
)

foreach ($name in $rootFiles) {
    $source = Join-Path $repoRoot $name
    if (Test-Path -LiteralPath $source) {
        Copy-Item -LiteralPath $source -Destination (Join-Path $stagingRoot $name)
    }
}

Get-ChildItem -LiteralPath $repoRoot -File -Filter "*.md" | ForEach-Object {
    Copy-Item -LiteralPath $_.FullName -Destination (Join-Path $stagingRoot $_.Name)
}

$excludedSegments = @(
    "node_modules", "dist", "__pycache__", ".pytest_cache", ".mypy_cache",
    ".ruff_cache", ".venv", ".runtime", "artifacts", "data"
)
$excludedExtensions = @(".pyc", ".pyo", ".log", ".db", ".sqlite", ".sqlite3")

foreach ($rootName in $allowedRoots) {
    $sourceRoot = Join-Path $repoRoot $rootName
    if (-not (Test-Path -LiteralPath $sourceRoot)) { continue }
    Get-ChildItem -LiteralPath $sourceRoot -Recurse -File | ForEach-Object {
        $relative = $_.FullName.Substring($repoRoot.Length + 1)
        $segments = $relative -split '[\\/]'
        if ($segments | Where-Object { $excludedSegments -contains $_ }) { return }
        if ($excludedExtensions -contains $_.Extension.ToLowerInvariant()) { return }
        if ($_.Name -eq ".env") { return }
        $destination = Join-Path $stagingRoot $relative
        New-Item -ItemType Directory -Path (Split-Path -Parent $destination) -Force | Out-Null
        Copy-Item -LiteralPath $_.FullName -Destination $destination
    }
}

$evidenceRoot = Join-Path $repoRoot "output\evidence"
Get-ChildItem -LiteralPath $evidenceRoot -Recurse -File | ForEach-Object {
    $relative = $_.FullName.Substring($repoRoot.Length + 1)
    $destination = Join-Path $stagingRoot $relative
    New-Item -ItemType Directory -Path (Split-Path -Parent $destination) -Force | Out-Null
    Copy-Item -LiteralPath $_.FullName -Destination $destination
}

$submissionRoot = Join-Path $repoRoot "output\submission"
Get-ChildItem -LiteralPath $submissionRoot -File | Where-Object {
    $_.Extension -ne ".zip" -and $_.Name -notlike "*.inspect.ndjson"
} | ForEach-Object {
    $relative = $_.FullName.Substring($repoRoot.Length + 1)
    $destination = Join-Path $stagingRoot $relative
    New-Item -ItemType Directory -Path (Split-Path -Parent $destination) -Force | Out-Null
    Copy-Item -LiteralPath $_.FullName -Destination $destination
}

if (Test-Path -LiteralPath $zipPath) {
    Remove-Item -LiteralPath $zipPath -Force
}
Compress-Archive -LiteralPath $stagingRoot -DestinationPath $zipPath -CompressionLevel Optimal

$zip = Get-Item -LiteralPath $zipPath
Write-Output "ZIP=$($zip.FullName)"
Write-Output "BYTES=$($zip.Length)"
