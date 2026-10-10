# Tracker

Where tickets for this repository live and how a skill publishes one (SETUP-2). Publishing is a
post and waits for a go-ahead (ASK-3).

## Tracker: <GitHub issues | GitLab issues | local markdown | other>

| Operation | Command or path |
|---|---|
| Create a ticket | `gh issue create --title "..." --body-file <file>` |
| Read a ticket | `gh issue view <number> --json number,title,body,labels,comments` |
| List open tickets | `gh issue list --state open --json number,title,labels` |
| Comment | `gh issue comment <number> --body-file <file>` |
| Apply or remove a label | `gh issue edit <number> --add-label "..." / --remove-label "..."` |
| Mark blocked by | native dependency link where available; otherwise a "Blocked by" line with full links |
| Close | `gh issue close <number> --comment "..."` |

For local markdown: tickets live at `.scratch/<feature>/issues/NN-slug.md`, numbered from 01 in
dependency order, with `Status:` and `Blocked by:` lines near the top; `.scratch/` is in
`.gitignore`.

## Labels

| Role | Label in this tracker | Meaning |
|---|---|---|
| needs-triage | `needs-triage` | a maintainer has not evaluated it |
| needs-info | `needs-info` | waiting on the reporter |
| ready-for-agent | `ready-for-agent` | specified well enough for an unattended agent |
| ready-for-human | `ready-for-human` | needs a person |
| wontfix | `wontfix` | will not be actioned |

## Ticket content

One ticket per real work item (TICKET-1), acceptance and blockers (TICKET-2), no infrastructure
identifiers, secret paths, partner URLs or names (TICKET-3), full links (TICKET-4).
