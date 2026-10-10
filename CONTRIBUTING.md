# Contributing

Contributions are welcome, however they were produced; a person signs off each commit.

- Sign off every commit (`git commit -s`): the Developer Certificate of Origin, in your own
  name. No tool trailers and no generated-with footers; the signer is the operator of record for
  the change (ATTR-1). The `conventions` check on every pull request refuses attribution text.
- One pull request per change, complete with tests, documentation and a changelog line
  (SLICE-1, SLICE-2). `just check` exits 0 before the pull request opens.
- A new rule starts in `rules/registry.json` with the next id in its prefix, a statement with an
  RFC 2119 word, its mechanisms and its owner skill, then a test if a mechanism enforces it,
  then the skill text that cites it. Run `agentic-sdlc coverage` and commit the regenerated
  `docs/coverage.md`.
- A change to a skill's wording passes `agentic-sdlc lint-voice --fail-on fail` and
  `agentic-sdlc check-skills`.
- Findings in review follow `skills/review-change`: one per thread, Conventional Comments, the
  rule broken, the required behaviour.

The maintainer merges. Discussion happens on the pull request; a decision that is hard to reverse
is recorded under `docs/adr/`.
