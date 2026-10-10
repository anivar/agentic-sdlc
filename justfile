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

plugin:
    claude plugin validate --strict .

# Decide a command as the hook would: just guard 'git add -A'
guard cmd:
    uv run agentic-sdlc guard "{{cmd}}" --cwd .

# Feed the hook the event Claude Code would send for a command, from this directory.
hook-try cmd:
    printf '%s' '{"tool_name":"Bash","tool_input":{"command":{{cmd}}},"cwd":"{{justfile_directory()}}"}' | python3 src/agentic_sdlc/hook.py; echo " (exit $?)"
