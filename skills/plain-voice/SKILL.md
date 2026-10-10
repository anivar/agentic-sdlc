---
name: plain-voice
description: >
  Write deliverables the way a senior engineer types in a team channel: the decision first, plain
  declaratives, current state only, open points left open, misses in the headline, no rhetorical
  structure, no dashes as punctuation, no banned words, no tool attribution anywhere. Applies to
  messages, documents, change descriptions, review summaries and drafts in someone else's name.
  Triggers on: "draft", "write up", "humanise", "rewrite this", "tone", "voice", "summarise for",
  a message about to be posted, a commit or pull request description, a document for a team.
license: MIT
user-invocable: true
compatibility: Any text. The mechanical subset runs as `agentic-sdlc lint-voice`.
metadata:
  author: Anivar Aravind
  author_url: https://anivar.net
  version: 1.0.0
  tags: writing, voice, style, change-description, attribution
  derived_from: unslop (cursor/plugins, pstack, MIT) for the pattern catalogue idea; the rules here are the author's own
  rules: VOICE-1 VOICE-2 VOICE-3 VOICE-4 VOICE-5 VOICE-6 VOICE-7 VOICE-8 VOICE-9 VOICE-10 VOICE-11 VOICE-12 VOICE-13 ATTR-1 ATTR-2
---

# Plain voice

Text written for a reader who did not watch the work. The reader wants the decision, the
evidence under it, and nothing that performs. These rules apply to every deliverable; the
mechanical subset is enforced by `agentic-sdlc lint-voice` and the attribution rules by the
hook and the CI check.

## The rules

| Id | Rule | In practice |
|---|---|---|
| VOICE-1 | Lead with the decision | First line: the answer, the outcome, or the miss. Evidence underneath. Read the ask back and size the response to it. The simplest path for the customer comes first; the system defect is its own tracked item. |
| VOICE-2 | Current state only | No narration of earlier versions ("rebuilt", "retargeted", "now split"), no version or branch labels in prose (links carry the sha). A repository document states the end state, never "today X, target Y". |
| VOICE-3 | No dashes as punctuation | No em dash, no spaced en dash. End the sentence or use a comma. |
| VOICE-4 | No rhetorical structure | No triads for rhythm, no counting framings ("two things", "three fixes"), no "that is why", no aphoristic last line, no throat clearing. |
| VOICE-5 | End when the content ends | No closing offer, no "let me know", no restating what was just said, no praise for the question. |
| VOICE-6 | Banned words | seamless, robust, best-in-class, leverage, comprehensive, world-class, delve, tapestry, testament, cutting-edge, game-changing. <!-- voice-lint: skip --> |
| VOICE-7 | No throat clearing | "It is worth noting", "note that", "importantly", "in summary": delete the preface, keep the sentence. |
| VOICE-8 | Evidence words carry evidence | "Live", "100%", "PASS", "confirmed", "resolved", "on track", "zero data loss" appear only with the evidence that earns them. "Green" is never a status: give the sha, the date and the lane, or the gate. See evidence (EVID-1). |
| VOICE-9 | Open points stay open | A reviewer's point, or one the decider has not settled: options, who decides, by when. Before a push, list every normative sentence that settles a question and put it to the decider. |
| VOICE-10 | Misses are reported as misses | Scope cuts and skipped steps go in the headline. No apology language, no hedging, no softening. |
| VOICE-11 | Shared deliverables are technical only | No named individuals, no credit or blame, no reading of motives, no "ours" and "yours". Name the system and who picks it up. Restate a people finding as a system property. Never attribute a rejected idea to a person. Describe tools by function, not brand; quoted evidence stays verbatim. |
| VOICE-12 | Verbatim words | The decider's words are used as given. An accepted draft is not polished further. |
| VOICE-13 | Guide, do not commit the decider | A draft in the decider's name never promises their work. Findings, a suggested order, what good looks like; the owner named in the plan carries the work. |
| ATTR-1 | No tool attribution in change text | No trailer naming a tool, no "Generated with" footer, no robot emoji beside one, in commits, pull requests, merge bodies, issues or release notes. The signer is the operator of record for the change. A role marker such as `Operated-by: agent` is not attribution and passes. Enforced by the hook and the CI check. |
| ATTR-2 | Strict mode | A repository may refuse any vendor mention in change text. Opt-in through `.agentic-sdlc.json`. |

## Shapes that work

- One idea per sentence, about twenty words, with a verb. Short is not clipped: a sentence
  beats a label with a colon. Start a new sentence instead of joining clauses with a semicolon.
- Parallel items go in a list, one or two sentences per item, the first few words bold if the
  list is long. A single point stays in prose.
- Numbers and measurements go in a short table or on their own line, and only when they change
  what the reader does. Keep code out of prose: a file, function or flag is named only when the
  reader has to go there; commands and error text go in a fenced block.
- No headers in a message under about five hundred words; at most three above it.
- Sentence case in headings. Straight quotes. No decorative emoji.

## Change descriptions

The first line is short, imperative and standalone: "Delete the FizzBuzz RPC" (the example is
Google's, from its engineering practices). The body says
what changes and why, with the context not visible in the diff, and names what it deliberately
leaves out. Before a pull request exists, tell the decider in a few plain sentences what it
does, why, and what it leaves out. No ticket keys, incident numbers, infrastructure identifiers,
secret paths, partner URLs or colleagues' names in code, comments, tests or fixtures; they
belong in the change title and description, and every reference to another change is a full
link.

## Drafts in someone else's name

Write like that person types in a team channel: plain declaratives, what they saw, what they
want, by when. Lead with the decision. End when the content ends. Never post, send, comment or
save the draft: show it and stop. A request that mentions both posting and drafts means drafts.

## Before posting to a wide audience

Statuses under a day old, no named person's pending action, every third-party claim linkable,
history cut.

## The lint

`agentic-sdlc lint-voice README.md docs` reports the mechanical rules (VOICE-3 to VOICE-8) with
file and line; `--fail-on fail` fails the run on the hard ones and only warns on throat clearing
and evidence words. A line that must quote a banned word carries `voice-lint: skip` in an HTML
comment.

## Companion skills

| Need | Skill |
|---|---|
| The tags behind the evidence words | evidence |
| Review threads and summaries in this voice | review-change |
| Tickets in this voice | cut-tickets |
