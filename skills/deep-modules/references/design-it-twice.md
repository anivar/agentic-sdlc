# Design it twice

Ousterhout's pattern: the first idea is rarely the best. When the decider wants alternative interfaces for a chosen
deepening candidate, and has agreed to a fan-out (DESIGN-5), run this pattern.

## 1. Frame the problem space

Write a short explanation for the decider: the constraints any new interface must satisfy, the
dependencies and their category (see `deepening.md`), and a rough code sketch that makes the
constraints concrete without proposing a design. Show it, then proceed; the decider reads while
the agents work.

## 2. Fan out

Three or more agents in parallel, each with a separate technical brief (file paths, coupling,
dependency category, what sits behind the seam) and a different constraint:

- minimise the interface: one to three entry points, maximum payback per entry point;
- maximise flexibility: many use cases and extension points;
- optimise for the most common caller: the default case is trivial;
- ports and adapters for the cross-seam dependencies, when they exist.

Include the vocabulary from SKILL.md and the project's glossary in every brief so the designs
name things consistently. Never inline large data into a brief; point at files.

Each agent returns: the interface (types, methods, parameters, invariants, ordering, error
modes), a usage example, what the implementation hides, the dependency strategy and adapters,
and where payback is high and where it is thin.

## 3. Present and compare

Present the designs one at a time, then compare in prose on depth, locality and seam placement.
Give a recommendation, or a hybrid when parts combine well. The decider wants a strong read,
not a menu. A choice that is hard to reverse and surprising gets a decision record (DECIDE-1).
