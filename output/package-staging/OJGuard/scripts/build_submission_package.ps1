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
    "skills", "demo", "benchmark", "scripts", "tests", "materials"
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
$reviewedDeckItem = Get-ChildItem -LiteralPath $submissionRoot -File -Filter "*.compact.pptx" |
    Select-Object -First 1
$canonicalDeckItem = Get-ChildItem -LiteralPath $submissionRoot -File -Filter "*.pptx" |
    Where-Object {
        $_.Name -notlike "*.compact.pptx" -and
        $_.Name -notlike "*_12*.pptx"
    } |
    Select-Object -First 1
Get-ChildItem -LiteralPath $submissionRoot -File | Where-Object {
    $_.Extension -ne ".zip" -and
    $_.Name -notlike "*.inspect.ndjson" -and
    $_.Name -notlike "*.compact.pptx" -and
    $_.Name -notlike "*_12*.pptx" -and
    $_.Name -notlike "*_12*.pdf" -and
    $_.Name -notlike '~$*'
} | ForEach-Object {
    $relative = $_.FullName.Substring($repoRoot.Length + 1)
    $destination = Join-Path $stagingRoot $relative
    New-Item -ItemType Directory -Path (Split-Path -Parent $destination) -Force | Out-Null
    $sourceFile = $_.FullName
    if (
        $reviewedDeckItem -and
        $canonicalDeckItem -and
        $_.FullName -eq $canonicalDeckItem.FullName
    ) {
        $sourceFile = $reviewedDeckItem.FullName
    }
    Copy-Item -LiteralPath $sourceFile -Destination $destination
}

if (Test-Path -LiteralPath $zipPath) {
    Remove-Item -LiteralPath $zipPath -Force
}

# Compress-Archive writes Windows separators and can produce ambiguous Unicode
# filenames for non-Windows extractors. Build the archive explicitly with UTF-8
# entry names and POSIX separators so Chinese documentation remains portable.
Add-Type -AssemblyName System.IO.Compression
$zipStream = [IO.File]::Open($zipPath, [IO.FileMode]::CreateNew)
$archive = [IO.Compression.ZipArchive]::new(
    $zipStream,
    [IO.Compression.ZipArchiveMode]::Create,
    $false
)
try {
    Get-ChildItem -LiteralPath $stagingRoot -Recurse -File |
        Sort-Object FullName |
        ForEach-Object {
            $entryName = $_.FullName.Substring($stagingBase.Length + 1).Replace('\', '/')
            $entry = $archive.CreateEntry(
                $entryName,
                [IO.Compression.CompressionLevel]::Optimal
            )
            $sourceStream = $_.OpenRead()
            $entryStream = $entry.Open()
            try {
                $sourceStream.CopyTo($entryStream)
            } finally {
                $entryStream.Dispose()
                $sourceStream.Dispose()
            }
        }
} finally {
    $archive.Dispose()
    $zipStream.Dispose()
}

$zip = Get-Item -LiteralPath $zipPath
Write-Output "ZIP=$($zip.FullName)"
Write-Output "BYTES=$($zip.Length)"
