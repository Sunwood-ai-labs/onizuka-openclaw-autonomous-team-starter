param(
    [Parameter(ValueFromRemainingArguments = $true)]
    [string[]]$Args
)

$ErrorActionPreference = "Stop"
$repoRoot = Split-Path -Parent $PSScriptRoot
uv run --project $repoRoot openclaw-podman mattermost @Args
exit $LASTEXITCODE
