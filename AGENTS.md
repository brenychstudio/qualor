# QUALOR development rules

- Read `docs/00_CANONICAL_BRIEF_UA.md` before implementation. It is the source of truth.
- Respect the assigned task ID and scope. Make minimal diffs; no hidden feature expansion.
- Use RED/GREEN TDD for behavioral changes. Run verification before claiming PASS.
- Never import proprietary code from BDB, Weekfield, Native Site Control, Distribution Desk or other products.
- `UNKNOWN != PASS`. Keep FIXTURE, REPLAY and LIVE explicitly distinct. Never simulate live access or AWS success.
- External application submission functionality is prohibited.
- Never commit secrets, credentials, `.env`, private runtime state or local machine reports. Keep local reports in ignored `.qualor/local/`.
- No paid cloud call unless the current task explicitly authorizes it. No infrastructure creation during bootstrap.
- Keep GitHub PRIVATE unless the owner explicitly authorizes a visibility change. Never merge a PR without authorization.
- Report exact before/after HEADs, branch, test commands, results/counts, blockers and push/PR state.
- Canonical changes require an explicit owner-approved change record. Preserve canonical bytes and verify the recorded SHA-256.
- Run `scripts/verify.ps1` and inspect Git status before finishing. Leave a clean worktree.
