# Governance

## The maintenance covenant

This project is one maintainer's work, published under the MIT license. If maintenance stops:

- Fork it. The license already permits it; no permission is needed or given.
- `rules/registry.json` is the specification. The rule ids, statements, mechanisms and
  decisions there are the contract that the hook, the git hooks, the CI workflow and the
  skills implement, and a fork or a reimplementation can build against the registry alone.
- The decision record a repository keeps (`decisions.jsonl`) is plain JSON Lines under the
  repository's own `.git/`; it is portable, and nothing in it leaves the machine.

## Rule ids

An id is never reused or renumbered. A rule that stops applying is marked
`status: deprecated` in the registry with `replaced_by` naming its successor, and the
changelog entry for the release names the decision record under `docs/adr/` that retired it.
`agentic-sdlc validate` enforces the shape.

## Changing a rule

Open an issue with the rule proposal template (`.github/ISSUE_TEMPLATE/rule_proposal.md`):
the statement with its RFC 2119 word, the mechanism and decision, the owner skill, and the
evidence. A rule only a skill carries is text an agent follows; the template asks for that to
be said. Rule changes land as pull requests, and the registry, the decision code and the
workflows require the maintainer's review (`.github/CODEOWNERS`).

## Security

Report a vulnerability privately, per [SECURITY.md](SECURITY.md). Everything else, including
a rule that refuses something it should not, is a public issue.
