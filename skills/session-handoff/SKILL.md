---
name: session-handoff
description: >
  Keep work coherent across sessions, compactions and full context windows. State lives in files,
  not the conversation: a progress file and a JSON feature list whose entries later sessions
  change only in their status and evidence. Each session starts by reading them, the git log and
  the basic check, takes one feature, and ends with a checkpoint commit. A feature passes only on
  a recorded end-to-end check. Go-aheads, boundaries and decisions are written down when they are
  settled, because compaction keeps only a summary. Knowledge that outlives the task moves to the
  repository. Triggers on: "pick up where we left off", "resume", "continue the work", "new
  session", "after compaction", "the context is full", "context rot", "handoff", "progress file",
  "feature list", "multi-session", "long task", "remember this for next time", "what did we
  decide".
license: MIT
compatibility: Any agent that reads and writes files in a git repository; the compaction notes describe Claude Code as documented in November 2026.
metadata:
  author: Anivar Aravind
  author_url: https://anivar.net
  version: 1.0.0
  tags: long-running, context, memory, compaction, handoff, progress
  derived_from: the long-running harness posts and the context-engineering post on Anthropic's engineering blog for the progress file, the JSON feature list, the start-up routine and structured note-taking; the rest is the author's own
  rules: HANDOFF-1 HANDOFF-2 HANDOFF-3 HANDOFF-4 HANDOFF-5 RUN-3 EVID-1 DECIDE-1 EVID-10 SETUP-1
---

# Session handoff

A conversation is working memory. It fills, it gets less reliable as it grows, and compaction
cuts it to a summary. Files in the working tree are the memory that lasts. Keep the state of long
work in them, and start every session from them.

## The rules

| Id | Rule | In practice |
|---|---|---|
| HANDOFF-1 | State that spans sessions lives in files | `.agent/progress.md` and `.agent/features.json` on the working branch. The feature list is JSON because a model rewrites Markdown more freely than JSON; later sessions change only `status` and `evidence`. |
| HANDOFF-2 | A session starts by reading and ends by committing | Start: `git log --oneline -20`, the progress file, the feature list, then the basic check (`just check`, or what the repository's agent file names). Fix a broken tree before new work. End: a checkpoint commit and a progress entry, leaving a tree that could merge. |
| HANDOFF-3 | One feature at a time, passing only on evidence | `status` becomes `passing` only with the check's command and result in `evidence`. Where the work is near the limit of what the model does reliably, a fresh agent or a person judges it, not the session that built it. |
| HANDOFF-4 | What is settled is written down when it is settled | A go-ahead, a boundary ("don't push"), a decision, a held call: into the progress file in the same turn. After a compaction or in a new session, re-read the progress file and the sources a claim rests on. The summary points at evidence; it is not evidence (EVID-1). |
| HANDOFF-5 | Knowledge that outlives the task goes to the repository | A convention to the repository's agent file (SETUP-1), a hard-to-reverse decision to a decision record (DECIDE-1), a finding to a dated research document (EVID-10). A session's own memory holds preferences and pointers to those files. |

## The files

`.agent/features.json`. Write it once at the start, from the plan or the ticket. Later sessions
change two fields.

```json
{
  "finish": "just check exits 0 and every feature has status passing",
  "features": [
    {
      "id": "F1",
      "what": "Search rejects a page token with 400",
      "check": "uv run pytest tests/test_search.py -k page_token",
      "status": "todo",
      "evidence": ""
    }
  ]
}
```

`status` is one of `todo`, `doing`, `passing`, `blocked`. `evidence` is the commit sha, the
command and its result: `4f2c1a9 uv run pytest tests/test_search.py -k page_token: 3 passed`.

`.agent/progress.md`. Append; never rewrite an earlier entry.

```markdown
# Progress: <task>
Finish condition: <the check that shows it> · Branch: <branch>

## Settled
| When (UTC) | What | Source |

## Held calls
| Call | Rule | Why it waits |

## Sessions
### <UTC date and time>
Did: <what changed, with shas> · Checked: <command> → <result> · Next: <the next item>
```

"Source" is where the decision came from: the user in chat, the launch prompt, a decision record.
An unattended run writes its held calls here and copies them into its run report (RUN-3).

The files are working files of the branch. Remove `.agent/` in the last commit before the pull
request unless the repository keeps it.

## Keep the window small

Accuracy falls as the window grows, even when the task stays the same, and text that resembles
the answer costs more than its length. So:

- Read by path and line range, not whole trees. Search first, then open what the search points to.
- Send a large read to a subagent that returns a short summary with its citations; re-open what
  it cites before relying on it.
- Before a long new stretch, start a fresh session from the progress file, or compact with a
  focus (`/compact keep the go-aheads, the held calls and the next step`). A fresh session that
  reads good files starts focused; a long one carries every stale turn.
- Keep the agent file short and specific. Each line of it loads into every session.

## What survives compaction in Claude Code

| Kept | Lost |
|---|---|
| The project-root `CLAUDE.md`, rules without `paths:`, auto memory and skill descriptions, re-read from disk | Anything said only in the conversation: a go-ahead, a boundary, a correction |
| Up to five recently changed files, re-read | Older file reads and tool output |
| Invoked skills, cut to the start of each and dropped oldest first when over budget | The end of a long skill |

A standing instruction belongs in a file, not in the chat. A skill author puts its rules at the
top of `SKILL.md`, because only the start may come back.

## Companion skills

| Need | Skill |
|---|---|
| A run that nobody watches | invoke `unattended-runs` |
| The slice each session lands | thin-slices |
| Where a decision or a research finding goes | decision-records |
| The agent file the next session reads | setup-conventions |
| The judge who did not build it | review-change |
| Calibrating what a progress entry claims | evidence |
