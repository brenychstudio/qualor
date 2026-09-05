# Stdio belongs to MCP. The Python launcher enforces identity and read-only mode.
[CmdletBinding()]
param()
$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest
$repositoryRoot = Split-Path -Parent $PSScriptRoot
Push-Location $repositoryRoot
try {
    uv run --locked --no-sync python "$PSScriptRoot\aws_bridge.py" proxy
    $result = $LASTEXITCODE
} finally {
    Pop-Location
}
exit $result
