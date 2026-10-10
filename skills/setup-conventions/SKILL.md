---
name: setup-conventions
description: >
  One-time repository setup for the agentic-sdlc skills: explore what the repository already
  has, confirm the choices with the decider, then write one "Rules that bind" block into the
  existing AGENTS.md or CLAUDE.md, docs/agents/tracker.md and docs/agents/conventions.md, and
  .agentic-sdlc.json with the hook settings, and prepare the reusable workflow and the ruleset
  import as a pull request. Run once per repository, by the person who owns it.
license: MIT
user-invocable: true
disable-model-invocation: true
argument-hint: "[repository root]"
compatibility: Any git repository on GitHub; the tracker section also records GitLab, local markdown or another tracker.
metadata:
  author: Anivar Aravind
  author_url: https://anivar.net
  version: 1.0.0
  tags: setup, conventions, agents-md, tracker, configuration
  derived_from: setup-matt-pocock-skills (mattpocock/skills, MIT) for the explore-confirm-write shape and the tracker templates; the configuration, workflow and ruleset steps are the author's own
  rules: SETUP-1 SETUP-2 SETUP-3 ASK-1 ASK-3 DECIDE-5 EVID-8
---

# Set up conventions

A prompt-driven setup, not a script. Explore, present what was found, confirm, then write.
Nothing is committed, pushed or imported without its own go-ahead (ASK-1, ASK-3).

## 1. Explore

Read what exists; assume nothing (EVID-8):

- `git remote -v`: which forge, which repository.
- `AGENTS.md` and `CLAUDE.md` at the root: which exists, whether a "Rules that bind" block is
  already there.
- `docs/agents/`, `.agentic-sdlc.json`, `GLOSSARY.md`, `docs/adr/`, `.scratch/`.
- `.github/workflows/`: an existing CI gate the ruleset should require.
- Rulesets and branch protection already applied (`gh ruleset list`).
- Monorepo signals: a workspace file, several packages with their own source.

## 2. Present and confirm

Lead each section with the recommended answer so the decider can accept it in a word.

- **Tracker**: GitHub issues when the remote is GitHub; GitLab when it is GitLab; local markdown
  under `.scratch/` for a repository without a remote; "other" recorded as a paragraph. Labels
  default to `needs-triage`, `needs-info`, `ready-for-agent`, `ready-for-human`, `wontfix`.
- **Protected branches**: `main` plus any release branch.
- **Attribution mode**: `patterns` (the default) or `strict`.
- **Decision records**: `docs/adr/` in the repository, or a private path the repository's
  `docs/agents/conventions.md` names.
- **Mechanisms**: the reusable workflow as a required check, and the ruleset import.

## 3. Write

In this order, each shown before it is written:

1. The "Rules that bind" block into the file that exists, in place if a block is already there
   (SETUP-1). Template: `templates/AGENTS-block.md` in this plugin. Never create a second agent
   file beside the existing one.
2. `docs/agents/tracker.md` (SETUP-2) from `templates/docs-agents/tracker.md`.
3. `docs/agents/conventions.md` from `templates/docs-agents/conventions.md`.
4. `.agentic-sdlc.json` from `templates/agentic-sdlc.json`, with the confirmed branches and
   mode. `agentic-sdlc validate` passes on it.
5. If the tracker is local markdown: `.scratch/` in `.gitignore`.
6. A workflow file that calls `anivar/agentic-sdlc/.github/workflows/conventions.yml` at a
   pinned tag, and the import command for `rulesets/main-protected.json` with the required
   check names adjusted to this repository's gate.

All of it lands as one reviewed pull request (SETUP-3). The ruleset import is run by the
decider after the merge, since it changes the forge's settings.

## 4. Done

Say which skills now read from these files, and that re-running the setup is only needed to
switch trackers or change the mode. Editing `docs/agents/*.md` and `.agentic-sdlc.json` by hand
is the normal path afterwards.

## Companion skills

| Need | Skill |
|---|---|
| The tickets the tracker file enables | cut-tickets |
| The records the conventions file points at | decision-records |
| Landing the setup pull request | thin-slices |
