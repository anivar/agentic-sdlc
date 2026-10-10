# The record carries accountability; origination is a role trailer, never a product name

Status: accepted · Date: 2026-10-10 · Decides: the maintainer

A sign-off names the person who answers for a change: the operator of record. A trailer or
footer naming a tool records which product was open, which readers mistake for accountability.
The hook refuses the second kind of marker. That leaves a question the maintainer's own
published work raises: a record should be able to say whether a human or an agent operated an
action, and the absence of a marker is not evidence that a human did.

The decision: the repository enforces accountability and makes origination available without
a product name. A trailer that names a role, `Operated-by: agent`, passes ATTR-1; a repository
that wants its history to carry origination adds it to its commit template, and one that does
not records accountability only and says so in its conventions file.

## Options considered

| Option | Why it lost |
|---|---|
| Refuse every marker, say nothing about origination | reads as hiding agent use; contradicts the glossary the maintainer publishes |
| Require an origination trailer on every agent commit | the hook cannot know who typed what; a required marker it cannot verify would be a false record |
| Allow vendor trailers as origination | a product name is marketing in the record and the first thing mistaken for accountability |

## Consequences

The README's "Why no tool attribution" section states both halves. ATTR-1's statement names the
role trailer as permitted. A future rule may ask for the trailer when a repository opts in.
