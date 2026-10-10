# Deepening

How to deepen a cluster of shallow modules safely, given its dependencies. Uses the vocabulary
in SKILL.md: module, interface, seam, adapter.

## Dependency categories

| Category | Example | How the deepened module is tested |
|---|---|---|
| In-process | pure computation, in-memory state | merge the modules, test through the new interface; no adapter |
| Local-substitutable | a database with a local stand-in, an in-memory file system | the stand-in runs in the suite; the seam is internal, no port at the external interface |
| Remote but owned | your own services across a network | a port at the seam; an HTTP, gRPC or queue adapter in production, an in-memory adapter in tests |
| True external | third-party services you do not control | the external dependency as an injected port; a mock adapter in tests |

Recommendation shape for the owned-remote case: define a port at the seam, implement a transport
adapter for production and an in-memory adapter for tests, so the logic sits in one deep module
even though it is deployed across a network.

## Seam discipline

- Two adapters make a seam (DESIGN-3). Do not introduce a port until production plus test, or
  two real variants, justify it.
- Internal seams stay internal. A deep module may have seams its own tests use; they are not part
  of the interface.

## Testing: replace, do not layer (DESIGN-4)

Delete the old unit tests on the shallow modules once tests at the deepened interface exist.
Write the new tests at the interface. Assert on observable outcomes, not internal state. A test
that has to change when the implementation changes was testing past the interface.
