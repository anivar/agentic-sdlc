# Security

## Reporting

Report a vulnerability through GitHub's private vulnerability reporting on this repository
(Security tab, "Report a vulnerability"). Do not open a public issue for it. Expect an
acknowledgement within seven days.

## What the hook does and does not do

The hook reads the JSON event Claude Code sends for a Bash tool call, parses the command string,
and may run read-only git commands in the working directory (`rev-parse`, `symbolic-ref`,
`show-ref`, `diff --cached`) and `gitleaks git --staged` when gitleaks is installed. It reads
message files the command names when they exist. It writes nothing, sends nothing over the
network, and prints no secret: a staged secret is reported by pattern name and line number only.

The hook is a guard, not a sandbox. It sees Bash tool calls only, it can be disabled by a user
setting, and a command the user types with the `!` prefix runs outside it. The CI check and the
ruleset are the backstops for what reaches the forge.

## Supply chain

The runtime path is the Python standard library. Development dependencies are pinned in
`uv.lock`. Workflow actions are pinned by commit sha.
