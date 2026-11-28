"""Claude Code hook: stdin JSON in, a permission decision out.

Runs as ``python3 hook.py`` (PreToolUse) or ``python3 hook.py --post`` (PostToolUse) with no
package installed, so the package directory is put on ``sys.path`` first. Exit 0 with no
output means "no decision", which hands the call to the normal permission flow. A decision
is one JSON object on stdout.

Three behaviours beyond the decision itself:

- In a permission mode that cannot prompt (``bypassPermissions``, ``dontAsk``) an ask or a
  deny is returned as a blocking error (exit 2), since the documentation states that such
  modes do not show a prompt; the reason tells the agent not to retry and to report the call.
- In agent mode, the default, the guard never asks (AGENT-1); when the launcher set
  ``AGENTIC_SDLC_UNATTENDED``, it never asks in confirm mode either (RUN-1). That mapping
  happens in ``guard`` before the decision reaches this module, except for a command the guard
  could not analyse, which is refused here unless the session is in confirm mode.
- With ``record.shadow`` (or ``AGENTIC_SDLC_SHADOW=1``) the decision is recorded and every
  command is let through, so a team can see what the hook would do before it refuses anything.
- After a commit ran (PostToolUse, which fires on success only), the message now at HEAD is
  checked for attribution when HEAD moved from the sha recorded before the command, which
  catches text the hook could not read beforehand (``-m "$(…)"``) without reporting an older
  commit the agent did not make. When nothing was recorded (a pair started before the state
  file existed), a recency guess stands in.

If the analysis itself fails, a command that looks like a commit, push or post gets an
``ask`` with the error in the reason (a refusal in agent mode), and any other command gets no
decision: a broken analysis must neither let gated work through silently nor block unrelated
commands. If the hook cannot load, or fails outside the analysis, every shell command is
refused with exit 2, which Claude Code and Codex both treat as a block. A failed file check
refuses only the guard's configuration and secret files.

Codex sends a file edit as ``apply_patch`` with the patch in ``tool_input.command``; every
file the patch names is checked as an edit.
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

PACKAGE_DIR = Path(__file__).resolve().parent.parent
if str(PACKAGE_DIR) not in sys.path:
    sys.path.insert(0, str(PACKAGE_DIR))

LOAD_ERROR: Exception | None = None
try:
    from agentic_sdlc import command as command_mod  # noqa: E402
    from agentic_sdlc import config as config_mod  # noqa: E402
    from agentic_sdlc import guard, record, text  # noqa: E402
except Exception as exc:  # noqa: BLE001 - a broken install must refuse, not let calls through
    LOAD_ERROR = exc

NO_PROMPT_MODES = {"bypassPermissions", "dontAsk"}
FILE_TOOLS = {"Read", "Grep", "Edit", "Write", "MultiEdit", "NotebookEdit"}
# Codex sends a file edit as one patch, with the patch text in tool_input.command.
PATCH_TOOLS = {"apply_patch"}
RECENT_COMMIT_SECONDS = 300


class Call:
    """One tool call as the hook sees it."""

    def __init__(self, event: dict) -> None:
        self.tool: str = event.get("tool_name", "") or ""
        tool_input = event.get("tool_input") or {}
        self.input: dict = tool_input if isinstance(tool_input, dict) else {}
        cwd = event.get("cwd")
        self.cwd: Path = Path(cwd) if isinstance(cwd, str) and cwd else Path.cwd()
        self.mode: str = event.get("permission_mode") or ""
        self.event: dict = event

    @property
    def takes_ask(self) -> bool:
        """Whether the agent behind the event can show a prompt for an ask. Codex marks its hook
        events with a turn id and accepts only deny from a PreToolUse hook, so an ask from it
        would be dropped; there it is refused instead."""
        return "turn_id" not in self.event

    @property
    def command(self) -> str:
        value = self.input.get("command")
        return value if isinstance(value, str) else ""

    @property
    def path(self) -> str:
        for key in ("file_path", "notebook_path", "path"):
            value = self.input.get(key)
            if isinstance(value, str) and value:
                return value
        return ""


# The reason an ask gets where the agent cannot show a prompt (Codex accepts only deny).
NO_ASK_HELD = (
    "this agent cannot show a prompt, so the call is refused. Do not retry it: carry on with the "
    "next step and list it as a held call so a person can run it"
)


def output(permission: str, reason: str) -> None:
    payload = {
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": permission,
            "permissionDecisionReason": reason,
        }
    }
    sys.stdout.write(json.dumps(payload))
    sys.stdout.flush()


def block(reason: str) -> int:
    sys.stderr.write(reason + "\n")
    sys.stderr.flush()
    return 2


def report_error(exc: Exception) -> None:
    sys.stderr.write(f"agentic-sdlc hook error: {exc!r}\n")


def read_event() -> dict | None:
    raw = sys.stdin.read()
    try:
        event = json.loads(raw) if raw.strip() else {}
    except ValueError:
        return None
    return event if isinstance(event, dict) else None


def main(argv: list[str] | None = None) -> int:
    """Exit 2 with the reason on stderr blocks a call in Claude Code and in Codex alike, so a
    hook that cannot load or crashes refuses shell commands instead of letting them run."""
    argv = sys.argv[1:] if argv is None else argv
    event = read_event()
    if event is None:
        return 0
    tool = event.get("tool_name") or ""
    before = "--post" not in argv
    if LOAD_ERROR is not None:
        if before and tool == "Bash":
            return block(
                f"agentic-sdlc could not load ({LOAD_ERROR!r}), so its refusal rules cannot run "
                "and every shell command is refused. Do not retry: a person reinstalls the plugin "
                "or disables it"
            )
        return 0
    try:
        return dispatch(Call(event), argv)
    except Exception as exc:  # noqa: BLE001 - fail closed for the shell, open for the rest
        report_error(exc)
        if before and tool == "Bash":
            return block(
                f"agentic-sdlc failed on this call ({exc!r}), so its refusal rules never ran and "
                "the call is refused. Do not retry it: carry on with the next step and list it as "
                "a held call"
            )
        return 0


def dispatch(call: Call, argv: list[str]) -> int:
    if "--post" in argv:
        return after_bash(call) if call.tool == "Bash" and call.command.strip() else 0
    if call.tool in FILE_TOOLS:
        return before_file(call)
    if call.tool in PATCH_TOOLS and call.command.strip():
        return before_patch(call)
    if call.tool == "Bash" and call.command.strip():
        return before_bash(call)
    return 0


def before_bash(call: Call) -> int:
    started = time.perf_counter()
    cfg: config_mod.Config | None = None
    try:
        cfg = config_mod.load(call.cwd)
        decision = guard.decide(call.command, call.cwd, cfg)
    except Exception as exc:  # noqa: BLE001 - the hook must never crash the session
        report_error(exc)
        if guard.looks_gated(call.command):
            if config_mod.unattended_from_env():
                output(
                    "deny",
                    f"agentic-sdlc could not analyse this command ({exc!r}); RUN-1: "
                    + guard.UNATTENDED_HELD,
                )
            elif agent_mode(cfg):
                output(
                    "deny",
                    f"agentic-sdlc could not analyse this command ({exc!r}), so its refusal rules "
                    "never ran; AGENT-1: " + guard.AGENT_HELD,
                )
            else:
                ask(
                    call,
                    f"agentic-sdlc could not analyse this command ({exc!r}); confirm it yourself",
                )
        return 0
    parsed = command_mod.parse(call.command, call.cwd)
    committed = [f for f in parsed.commands if f.is_commit and not f.dry_run]
    if committed:
        record.write_pre_head(call.cwd, guard.head_sha(committed[-1].workdir or call.cwd))
    return settle(
        call,
        cfg,
        decision,
        subject=call.command,
        kinds=[c.kind for c in parsed.commands],
        ms=(time.perf_counter() - started) * 1000,
    )


def agent_mode(cfg: config_mod.Config | None) -> bool:
    """The mode for a command the guard could not analyse: the loaded configuration's, or the
    default (agent) when even that failed, unless the environment sets confirm (AGENT-1)."""
    return cfg.agent_decides if cfg is not None else config_mod.Config().agent_decides


def before_file(call: Call) -> int:
    try:
        cfg = config_mod.load(call.cwd)
        decision = guard.decide_file(call.tool, call.path, call.cwd, cfg)
    except Exception as exc:  # noqa: BLE001
        report_error(exc)
        return refuse_guarded_paths([call.path], exc)
    if decision.permission == "allow" and not record.must_record(decision.rules):
        return 0  # file reads are not recorded; only a decision is
    return settle(call, cfg, decision, subject=call.path, kinds=["file"], ms=0.0)


def before_patch(call: Call) -> int:
    """A Codex patch: GUARD-2 for every file it adds, updates, deletes or moves to."""
    paths: list[str] = []
    try:
        paths = guard.patch_paths(call.command)
        cfg = config_mod.load(call.cwd)
        decision = guard.decide_patch(call.command, call.cwd, cfg)
    except Exception as exc:  # noqa: BLE001
        report_error(exc)
        return refuse_guarded_paths(paths, exc)
    if decision.permission == "allow" and not record.must_record(decision.rules):
        return 0
    return settle(call, cfg, decision, subject=", ".join(paths), kinds=["patch"], ms=0.0)


def refuse_guarded_paths(paths: list[str], exc: Exception) -> int:
    """When the file check fails, a guarded or secret path is refused and the rest pass."""
    hits = [p for p in paths if command_mod.is_guard_config(p) or command_mod.is_secret_file(p)]
    if not hits:
        return 0
    return block(
        f"agentic-sdlc could not check {', '.join(hits[:3])} ({exc!r}); the guard's configuration "
        "and secret files are refused until it can. Do not retry: list it as a held call"
    )


def settle(
    call: Call,
    cfg: config_mod.Config,
    decision: guard.Decision,
    *,
    subject: str,
    kinds: list[str],
    ms: float,
) -> int:
    """Record the decision when the repository keeps a record or the agent decided in place of
    a person (record.must_record), then return it the way the
    permission mode can take it: nothing for allow or shadow, a blocking error where no prompt
    is possible, the JSON decision otherwise."""
    if cfg.recording or record.must_record(decision.rules):
        record.append(
            cfg,
            call.cwd,
            record.entry(
                event="PreToolUse",
                tool=call.tool,
                decision=decision.permission,
                rules=decision.rules,
                reasons=decision.reasons,
                mode=call.mode,
                command=subject,
                kinds=kinds,
                ms=ms,
                shadow=cfg.shadow,
            ),
        )
    if cfg.shadow or decision.permission == "allow":
        return 0
    if call.mode in NO_PROMPT_MODES:
        return block(
            f"agentic-sdlc {decision.reason}; this permission mode cannot prompt, so the call is "
            "refused. Do not retry it: carry on with the next step and list it in the run report "
            "so a person can run it"
        )
    if decision.permission == "ask":
        ask(call, "agentic-sdlc " + decision.reason)
    else:
        output(decision.permission, "agentic-sdlc " + decision.reason)
    return 0


def ask(call: Call, reason: str) -> None:
    """An ask where the agent can show one; a refusal with the same reason where it cannot."""
    if call.takes_ask:
        output("ask", reason)
    else:
        output("deny", reason + "; " + NO_ASK_HELD)


def after_bash(call: Call) -> int:
    """PostToolUse: if the command committed, check the message that landed at HEAD."""
    try:
        cfg = config_mod.load(call.cwd)
        parsed = command_mod.parse(call.command, call.cwd)
        committed = [f for f in parsed.commands if f.is_commit and not f.dry_run]
        if not committed:
            return 0
        where = committed[-1].workdir or call.cwd
        stored, pre_sha = record.read_pre_head(call.cwd)
        if stored:
            record.drop_pre_head(call.cwd)
            current = guard.head_sha(where)
            if current is not None and current == pre_sha:
                return 0  # HEAD did not move: the commit did not land, nothing to check
            # HEAD moved, or a first commit replaced an unborn HEAD: check what landed.
        else:
            # The weak fallback, kept for a pair that started before the state file existed
            # (an upgrade in flight): a committer timestamp is forgeable, so this only
            # guesses that HEAD is fresh.
            age = guard.head_age_seconds(where)
            if age is None or age > RECENT_COMMIT_SECONDS:
                return 0  # the commit did not land, or HEAD is an older commit
        findings = text.attribution_findings(guard.head_message(where), cfg)
    except Exception as exc:  # noqa: BLE001
        report_error(exc)
        return 0
    if not findings:
        return 0
    described = "; ".join(f.describe() for f in findings[:3])
    if cfg.recording:
        record.append(
            cfg,
            call.cwd,
            record.entry(
                event="PostToolUse",
                tool="Bash",
                decision="deny",
                rules=sorted({f.rule for f in findings}),
                reasons=[described],
                mode=call.mode,
                command=call.command,
                kinds=["git-commit"],
                ms=0.0,
                shadow=cfg.shadow,
            ),
        )
    if cfg.shadow:
        return 0
    return block(
        f"agentic-sdlc: the commit that just landed carries tool attribution ({described}); "
        "amend it without the trailer or footer (git commit --amend) before anything is pushed"
    )


if __name__ == "__main__":
    sys.exit(main())
