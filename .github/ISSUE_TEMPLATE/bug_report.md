---
name: Bug report
about: A command the hook decided wrongly, a check that failed when it should pass, or the reverse
title: ""
labels: needs-triage
---

## The command or input

The exact command the agent ran, or the text the check scanned. Replace any secret with the
word `<redacted>`; never paste a token.

```
```

## Expected decision

allow, ask or deny, and the rule id you expected (see `rules/registry.json`).

## Actual decision

What the hook or check returned, with its reason line.

## Environment

- agentic-sdlc version or commit:
- `python3 --version` on the machine that ran the hook:
- Claude Code version (`claude --version`), or the agent and version for a CI or git-hook report:
- Operating system:

## Reproduction

The smallest sequence that shows it. `uvx --from git+https://github.com/anivar/agentic-sdlc agentic-sdlc guard '<command>'` is enough for a hook decision.
