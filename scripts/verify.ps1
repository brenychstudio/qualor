# All verification is local; no AWS credentials or cloud calls are required.
[CmdletBinding()]
param()

$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest
$repositoryRoot = Split-Path -Parent $PSScriptRoot

function Invoke-Gate {
    param([string]$Name, [scriptblock]$Command)
    Write-Output "GATE=$Name"
    & $Command
    if ($LASTEXITCODE -ne 0) {
        throw "Gate failed: $Name (exit $LASTEXITCODE)"
    }
}

Push-Location $repositoryRoot
try {
    Invoke-Gate 'Python environment sync' { uv sync --locked }
    Invoke-Gate 'Ruff' { uv run --locked ruff check . }
    Invoke-Gate 'Pytest' { uv run --locked pytest -q }
    Invoke-Gate 'Offline doctor' { uv run --locked qualor doctor }
    Invoke-Gate 'Frontend install from lockfile' { npm --prefix apps/web ci }
    Invoke-Gate 'Frontend typecheck and build' { npm --prefix apps/web run build }
    Write-Output 'GATE=Canonical and tracked secret-pattern sanity check'
    @'
import hashlib
import pathlib
import re
import subprocess

expected = "440db7b600d6ec170778035e39d93ce8cd5b8f20d49fd99bccf3174978536829"
canonical = pathlib.Path("docs/00_CANONICAL_BRIEF_UA.md")
for content in [canonical.read_bytes(), subprocess.check_output(["git", "show", ":" + canonical.as_posix()])]:
    if len(content) != 62438 or hashlib.sha256(content).hexdigest() != expected:
        raise SystemExit("CANONICAL_HASH_MATCH=BLOCKED")

patterns = [
    r"(?:AKIA|ASIA)[A-Z0-9]{16}",
    r"gh[pousr]_[A-Za-z0-9]{20,}",
    r"github_pat_[A-Za-z0-9_]{20,}",
    r"arn:(?:aws|aws-us-gov|aws-cn):[^\s\"']+",
    r"\b\d{12}\b",
    r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----",
    r"(?i)(?:aws_secret_access_key|aws_session_token|github_token)\s*[:=]\s*[\"']?[A-Za-z0-9/+_=-]{16,}",
]
paths = subprocess.check_output(["git", "ls-files", "-z"]).decode().split("\0")
for name in filter(None, paths):
    path = pathlib.PurePosixPath(name)
    forbidden_parts = {".qualor", ".venv", ".aws", ".ssh", "node_modules", "__pycache__"}
    if forbidden_parts.intersection(path.parts) or (
        path.name != ".env.example" and (path.name == ".env" or path.name.startswith(".env."))
    ) or path.suffix in {".pem", ".key", ".pfx", ".p12"} or path.name in {"credentials", ".npmrc"}:
        raise SystemExit("FORBIDDEN_TRACKED_FILE=" + name)
    # Scan both staged bytes and the working copy, including the immutable canonical.
    contents = [subprocess.check_output(["git", "show", ":" + name]), pathlib.Path(name).read_bytes()]
    for data in contents:
        text = data.decode("utf-8", errors="replace")
        if any(re.search(pattern, text) for pattern in patterns):
            raise SystemExit("SECRET_PATTERN_DETECTED_IN=" + name)
print("CANONICAL_HASH_MATCH=PASS")
print("SECRETS_SCAN=PASS")
'@ | uv run --locked python -
    if ($LASTEXITCODE -ne 0) { throw 'Canonical/secret-pattern gate failed' }
    Invoke-Gate 'Git diff whitespace' { git diff --check }
    Invoke-Gate 'Git staged whitespace' { git diff --cached --check }
    $status = @(git status --porcelain --untracked-files=all)
    if ($LASTEXITCODE -ne 0) { throw 'Git status failed' }
    if ($status.Count -gt 0) {
        Write-Output $status
        throw 'Git worktree is not clean; commit intended changes before final verification'
    }
    Write-Output 'WORKTREE=CLEAN'
    Write-Output 'VERIFY_SCRIPT=PASS'
} catch {
    Write-Error -Message $_.Exception.Message -ErrorAction Continue
    exit 1
} finally {
    Pop-Location
}
exit 0
