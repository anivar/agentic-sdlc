---
name: deep-modules
description: >
  The vocabulary and the moves for designing deep modules: a lot of behaviour behind a small
  interface at a clean seam, testable through that interface. Module, interface, implementation,
  depth, seam, adapter, payback, locality, used exactly. Deepening a cluster given its
  dependency category, and exploring alternative interfaces with parallel agents only after
  the decider agrees to the fan-out.
  Triggers on: "design the interface", "where should the seam go", "deepen this", "module
  boundary", "make this testable", "too many small modules", "ports and adapters", "design it
  twice", "which abstraction".
license: MIT
compatibility: Any codebase. The fan-out in design-it-twice needs an agent runtime that can run sub-agents.
metadata:
  author: Anivar Aravind
  author_url: https://anivar.net
  version: 1.0.0
  tags: design, modules, interfaces, seams, testability, architecture
  derived_from: codebase-design (mattpocock/skills, MIT) for the glossary, deepening and design-it-twice; the consent rule for fan-out is the author's own
  rules: DESIGN-1 DESIGN-2 DESIGN-3 DESIGN-4 DESIGN-5 TEST-1 DECIDE-1 VOICE-6
---

# Deep modules

Design deep modules: a lot of behaviour behind a small interface, placed at a clean seam,
testable through that interface. The aim is payback for callers, locality for maintainers, and
testability for everyone.

## Vocabulary

Use these words exactly in module design; do not substitute "component", "service" or "API"
for module and interface, or "boundary" for seam. "Boundary" keeps its other senses: a bounded
context, and the system boundary where test-first puts its mocks.

| Term | Is | Avoid |
|---|---|---|
| Module | Anything with an interface and an implementation: a function, a class, a package, a tier-spanning slice. | unit, component, service |
| Interface | Everything a caller must know to use the module correctly: types, invariants, ordering, error modes, required configuration, performance characteristics. | API, signature |
| Implementation | What is inside the module. | |
| Depth | Behaviour a caller or a test can exercise per unit of interface learned. Deep: a lot behind a little. Shallow: the interface is nearly as complex as the implementation. | |
| Seam | Michael Feathers' term: a place where behaviour can be altered without editing in that place; where a module's interface lives. Where the seam goes is its own decision. | boundary |
| Adapter | A concrete thing that satisfies an interface at a seam. A role, not a substance. | |
| Payback | What callers get from depth: one implementation pays back across N call sites and M tests. | leverage (Ousterhout's and the upstream's word; kept out of this set because VOICE-6 bans it as a verb) <!-- voice-lint: skip --> |
| Locality | What maintainers get from depth: change, bugs and knowledge concentrate in one place. | |

## The rules

| Id | Rule | In practice |
|---|---|---|
| DESIGN-1 | Deep modules | Fewer methods, simpler parameters, more hidden. The deletion test: delete the module; if complexity vanishes it was a pass-through, if it reappears across N callers it was earning its keep. |
| DESIGN-2 | The interface is the test surface | Callers and tests cross the same seam. Wanting to test past the interface means the module is the wrong shape. A module can have internal seams for its own tests without exposing them. |
| DESIGN-3 | Two adapters make a seam | One adapter is a hypothetical seam: indirection with no variation. Production plus test counts as two. |
| DESIGN-4 | Replace tests after deepening | Old tests at the shallow modules become waste once tests at the deepened interface exist; delete them. New tests assert observable outcomes through the interface and survive internal refactors. |
| DESIGN-5 | Design it twice, with consent | Ask before a fan-out. With consent, three or more agents each produce a radically different interface; compare on depth, locality and seam placement; recommend one, or a hybrid. Without consent, one design at a time. |

## Designing for testability

Accept dependencies, do not create them. Return results, do not produce side effects. Keep the
surface small: fewer methods mean fewer tests, fewer parameters mean simpler setup.

## Rejected framings

Depth as a ratio of implementation lines to interface lines rewards padding; depth is payback.
"Interface" as the language keyword or a class's public methods is too narrow. "Boundary" is
overloaded with bounded contexts; say seam or interface.

## Going deeper

- Deepening a cluster given its dependencies: `references/deepening.md`.
- Exploring alternative interfaces in parallel: `references/design-it-twice.md`.

## Companion skills

| Need | Skill |
|---|---|
| Agreeing the seams before tests (TEST-1) | invoke `test-first` after this skill |
| Recording a seam placement that is hard to reverse | decision-records |
| The questions that settle the design | grill-plan |

## Sources

John Ousterhout, A Philosophy of Software Design (deep modules, design it twice). Michael
Feathers, Working Effectively with Legacy Code (seams). codebase-design (mattpocock/skills, MIT).
