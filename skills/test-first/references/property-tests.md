# Property tests

Use a property test where a rule holds for every input: a total equals the sum of its parts, decoding an encoded value
returns the value, a state changes only through its transition table. The library generates the inputs, reports the
seed of a failure, and shrinks the failing input to a small case. Put the seed in the failure message.

## How to write one

- State the rule as a relation between results, or take it from the specification (TEST-3). Do not compute the
  expected value with the formula of the code under test. `total(a ++ b) == total(a) + total(b)` is a property.
  `total(lines) == sum(price * qty)` repeats the code.
- Build the inputs with the library's generators, so a failure shrinks.
- Data from a separate fake-data library does not shrink. Let the property library choose that library's seed, so a
  failure replays.
- Do not write a property over a constant input, for example `fc.property(fc.constant(null), ...)`. It generates
  nothing, and its counterexample does not identify the data that failed.
- Randomness is a system boundary (TEST-4). Seed it; do not mock it.

## Library per language

| Language | Library | Latest release, checked 2026-11-02 | Note |
|---|---|---|---|
| TypeScript, JavaScript | fast-check | 4.10.2 | |
| Python | Hypothesis | 6.170.14 | |
| Kotlin | Kotest property (`io.kotest:kotest-property`) | 6.2.6 | |
| Java | jqwik | 1.10.2 | Runs on JUnit Platform 1.14. In maintenance mode: dependency updates and crucial fixes only |
| C# | FsCheck, or CsCheck | 3.6.0; 5.0.0 | |
| Go | rapid (`pgregory.net/rapid`) | 1.3.0 | |
| Rust | proptest | 1.12.0 | |
| PHP | Eris (`giorgiosironi/eris`) | 1.3.0 | |
| Swift | swift-property-based (`x-sheep/swift-property-based`) | 2.0.1 | Runs in Swift Testing, shrinks, accepts a fixed seed. A small project |
| Dart, Flutter | kiri_check | 1.4.0 | Shrinks, and has stateful tests. A small project |
| Objective-C | None maintained | | Use a seeded loop |

## A seeded loop

Where no library fits, draw the inputs from a random source seeded by a fixed or logged value. Assert the rule on each
input, and print the seed and the input on failure. The loop replays a failure, but it does not shrink the input.
