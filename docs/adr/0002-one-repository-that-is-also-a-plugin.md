# One repository that is also a Claude Code plugin

Status: accepted · Date: 2026-10-10 · Decides: the maintainer

The maintainer's other skills follow a one-skill-per-repository pattern. This set deviates:
eleven skills, the hook, the CI check and the ruleset live in one repository that also carries
`.claude-plugin/plugin.json` and `marketplace.json`. A plugin is the only way the hook installs
with the skills, and a plugin needs its skills in one tree. The skills CLI installs the same
tree into every other agent (Verified: `npx skills add ./` placed all eleven on 2026-10-10).

## Options considered

| Option | Why it lost |
|---|---|
| One repository per skill plus a plugin repository | twelve repositories to keep in step; the plugin would copy or submodule the skills |
| Skills only, no plugin | the hook could not ship; the rules would be text only |

## Consequences

A Claude Code user installs the plugin and nothing else; a user of another agent installs with
the skills CLI and gets the skills without the hook. The README prescribes one path per tool so
a Claude Code user does not end up with duplicates.
