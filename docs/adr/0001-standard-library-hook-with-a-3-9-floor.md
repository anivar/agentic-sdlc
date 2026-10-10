# The hook is standard-library Python with a 3.9 floor

Status: accepted · Date: 2026-10-10 · Decides: the maintainer

The hook runs on every Bash tool call, on whatever machine installed the plugin, with nothing
installed first. A Node or shell-plus-jq hook would add a dependency the adopter has to have;
a Python hook that imports a package would need a virtual environment the plugin cannot create.
So the hook is Python that imports only the standard library, and it stays within the syntax of
Python 3.9 because the interpreter a stock macOS ships is 3.9.6 (Verified on 2026-10-10). The
suite runs on 3.9, 3.13 and 3.14 in CI so the floor cannot slip by accident.

## Options considered

| Option | Why it lost |
|---|---|
| Node script | Node is common on developer machines but not on every machine that runs an agent; `node` beside `python3` doubles what has to be present |
| Shell plus `jq` | `jq` is often absent; parsing a shell command inside a shell script is the wrong tool |
| Python with a dependency | nothing installs it; `${CLAUDE_PLUGIN_ROOT}` is read-only for the hook |

## Consequences

A machine without `python3` on `PATH` blocks every Bash call under `onFailure: block`; the
README says so. Windows needs `python3` to resolve to a real executable.
