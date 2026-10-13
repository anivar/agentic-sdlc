"""agentic-sdlc: skills and non-negotiable checks for a delivery process run with coding agents.

The package has one job: decide what a git or forge command is about to do and apply the
rules in ``rules/registry.json``. The Claude Code hook (``hook.py``) and the CI check
(``cli.py check-pr``) are thin adapters over the same functions.
"""

from importlib.metadata import PackageNotFoundError, version

try:
    __version__ = version("agentic-sdlc")
except PackageNotFoundError:  # running from a source checkout without installation
    __version__ = "0.0.0+dev"
