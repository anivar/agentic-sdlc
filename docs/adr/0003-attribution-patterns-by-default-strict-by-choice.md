# Attribution patterns are refused by default; any vendor mention only on request

Status: accepted · Date: 2026-10-10 · Decides: the maintainer

ATTR-1 refuses trailers naming a tool, generated-with footers and the robot emoji beside one.
It does not refuse the word "Claude" or "Copilot" in a commit subject, because this repository's
own history has to say "Add the Claude Code plugin manifest". A repository that wants no vendor
named anywhere in its change text sets `attribution.mode` to `strict` (ATTR-2) and accepts that
"Update the openai dependency" is then refused too.

## Options considered

| Option | Why it lost |
|---|---|
| Strict everywhere | this repository could not describe what it supports; adopters with vendor-named dependencies would turn the hook off |
| Patterns only, no strict mode | a repository that wants a vendor-free history would have nothing to turn on |

## Consequences

Two vendor lists: a wide one for trailer and footer context, where a match is unambiguous, and a
narrow one for strict mode, where "cursor" and "amp" are ordinary words. Both extend through
`attribution.vendors`.
