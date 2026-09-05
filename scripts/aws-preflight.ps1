# Read-only operator checks. No AWS inference or resource mutations.
[CmdletBinding()]
param()
$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest
$repositoryRoot = Split-Path -Parent $PSScriptRoot
Push-Location $repositoryRoot
try {
    uv run --locked --no-sync python "$PSScriptRoot\aws_bridge.py"
    $result = $LASTEXITCODE
} finally {
    Pop-Location
}
exit $result
