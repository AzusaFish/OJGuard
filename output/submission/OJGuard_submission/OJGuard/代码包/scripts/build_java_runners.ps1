$ErrorActionPreference = "Stop"

$workspace = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$dockerfile = Join-Path $workspace "runner\java\Dockerfile"
$context = Join-Path $workspace "runner"

docker build --file $dockerfile --build-arg JAVA_EXECUTION_MODE=normal `
    --tag ojguard-java-runtime:normal-17 $context
docker build --file $dockerfile --build-arg JAVA_EXECUTION_MODE=degraded `
    --tag ojguard-java-runtime:degraded-17 $context
