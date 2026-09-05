# Deterministic local schema export; no network, model or AWS calls.
[CmdletBinding()]
param([switch]$Check)

$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest
Push-Location (Split-Path -Parent $PSScriptRoot)
try {
    if ($Check) {
        uv run --locked --no-sync python -m qualor.schemas.export --check
    } else {
        uv run --locked --no-sync python -m qualor.schemas.export
    }
    if ($LASTEXITCODE -ne 0) { throw 'Schema export/check failed' }
} catch {
    Write-Error -Message $_.Exception.Message -ErrorAction Continue
    exit 1
} finally {
    Pop-Location
}
exit 0
