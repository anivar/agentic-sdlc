# Developer entry points. `just` runs the default recipe, which is the full gate.

default: check

# Everything CI runs, in order.
check: lint test validate skills voice coverage-check plugin

lint:
    uv run ruff check .
    uv run ruff format --check .

fmt:
    uv run ruff check --fix .
    uv run ruff format .

test:
    uv run pytest

# The hook must run on a stock macOS interpreter too.
test-stock:
    uv run --python /usr/bin/python3 --no-project --with pytest pytest

validate:
    uv run agentic-sdlc validate

skills:
    uv run agentic-sdlc check-skills

voice:
    uv run agentic-sdlc lint-voice README.md CHANGELOG.md docs skills --fail-on fail

coverage:
    uv run agentic-sdlc coverage

coverage-check:
    uv run agentic-sdlc coverage --check

# Compare the gh/glab verb tables with the installed CLIs (local --help only, no network).
verbs-check:
    uv run python scripts/check_verb_tables.py

plugin:
    claude plugin validate --strict .

# Behavioural cases under evals/, with and without the plugin. Each run is a real model call.
eval:
    claude plugin eval . --runs 1

# Install the native git hooks into this checkout.
hooks:
    uv run agentic-sdlc hooks install

# Decide a command as the hook would: just guard 'git add -A'
guard cmd:
    uv run agentic-sdlc guard "{{cmd}}" --cwd .

# Feed the hook the event Claude Code would send for a command, from this directory.
hook-try cmd:
    printf '%s' '{"tool_name":"Bash","tool_input":{"command":{{cmd}}},"cwd":"{{justfile_directory()}}"}' | python3 src/agentic_sdlc/hook.py; echo " (exit $?)"

# Build the distribution into dist/. Releasing is the signed tag: release.yml writes the
# GitHub release from the changelog section.
release:
    uv build

# Load the plugin into a throwaway Codex home and check that Codex sees every skill.
codex-check:
    #!/usr/bin/env sh
    set -eu
    # Outside the repository, which Codex copies into its home, and outside the temp directory.
    home="${XDG_CACHE_HOME:-$HOME/.cache}/agentic-sdlc/codex-home"
    rm -rf "$home" && mkdir -p "$home"
    export CODEX_HOME="$home"
    codex plugin marketplace add "{{justfile_directory()}}" >/dev/null
    codex plugin add agentic-sdlc@agentic-sdlc >/dev/null
    codex debug prompt-input > "$home/prompt.json"
    for dir in skills/*/; do grep -q "agentic-sdlc:$(basename "$dir")" "$home/prompt.json" || { echo "codex does not load $(basename "$dir")"; exit 1; }; done
    echo "codex loads every skill"

# Newer versions of the development dependencies, if any.
outdated:
    uv tree --outdated
