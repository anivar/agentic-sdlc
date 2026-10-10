# Ticket template

On a tracker (one issue per ticket, blockers first so edges can reference real identifiers):

```markdown
## Parent
<Full link to the parent item, when there is one.>

## What to build
<The end-to-end behaviour this ticket makes work, from the user's perspective.>

## Acceptance
- [ ] <criterion someone else can check>
- [ ] <criterion>

## Blocked by
- <full link>, or "None (can start now)". Omit when native dependency links were set.
```

Local markdown (`.scratch/<feature>/issues/NN-slug.md`, numbered from 01 in dependency order):

```markdown
# NN: <title>

What to build: <one paragraph, user's perspective>
Blocked by: <numbers and titles, or "None (can start now)">
Status: ready

- [ ] <acceptance criterion>
- [ ] <acceptance criterion>
```

Rules of the text: plain voice (VOICE-1, VOICE-11); no infrastructure identifiers, secret paths,
partner URLs or names (TICKET-3); full links only (TICKET-4).
