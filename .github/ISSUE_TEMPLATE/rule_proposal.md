---
name: Rule proposal
about: A new rule for the registry, or a change to an existing one
title: ""
labels: needs-triage
---

## Statement

One or two sentences with the key words in capitals (MUST, MUST NOT, SHOULD, SHOULD NOT, MAY).
Say what the rule applies to and when it does not.

## Mechanism

Which of hook, ci, ruleset or skill would enforce it, and the decision (deny or ask) if the hook
does. A rule only a skill carries is text an agent follows; say so if that is the intent.

## Owner skill

The skill whose text would carry the rule, or the new skill it needs.

## Evidence

What went wrong without the rule, with a command, a diff or a link. A rule proposed from a
preference rather than an incident says so.

## Compatibility

Who the rule would refuse today that it should not, and how a repository switches it off.
