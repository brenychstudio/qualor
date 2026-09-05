# Local generation from committed canonical schemas; install with npm ci first.
[CmdletBinding()]
param([switch]$Check)

$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest
Push-Location (Split-Path -Parent $PSScriptRoot)
try {
    if ($Check) {
        node apps/web/scripts/generate-domain.mjs --check
    } else {
        node apps/web/scripts/generate-domain.mjs
    }
    if ($LASTEXITCODE -ne 0) { throw 'Type generation/check failed' }
} catch {
    Write-Error -Message $_.Exception.Message -ErrorAction Continue
    exit 1
} finally {
    Pop-Location
}
exit 0
