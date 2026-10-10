"""Shell command analysis for the git and forge rules.

A Bash tool call carries one string that may hold several simple commands joined by
``&&``, ``||``, ``;``, pipes and newlines, plus heredocs. This module splits it, classifies
each simple command and extracts the change text it carries (commit messages, PR bodies,
issue text, release notes) so the text rules can run before anything is sent.

The parser is deliberately tolerant: it never raises on odd input, and when it cannot
tell, it reports what it saw and lets ``guard`` decide conservatively.
"""

from __future__ import annotations

import re
import shlex
import subprocess
from collections.abc import Iterable
from dataclasses import dataclass, field
from pathlib import Path

OPERATORS = {"&&", "||", ";", ";;", "|", "|&", "&", "(", ")", "{", "}"}
# Programs that run another program: dropped, with their own options, before classification.
# The value is the set of options that take an argument.
WRAPPER_OPTION_ARGS: dict[str, set[str]] = {
    "command": set(),
    "exec": {"-a"},
    "builtin": set(),
    "nohup": set(),
    "time": {"-f", "--format", "-o", "--output"},
    "sudo": {"-u", "-g", "-C", "-D", "-h", "-p", "-r", "-t", "-T", "-U", "--user", "--group"},
    "doas": {"-u", "-C"},
    "env": {"-u", "--unset", "-C", "--chdir", "-S", "--split-string"},
    "nice": {"-n", "--adjustment"},
    "ionice": {"-c", "-n", "-p", "--class", "--classdata"},
    "timeout": {"-k", "--kill-after", "-s", "--signal"},
    "xargs": {
        "-n",
        "-I",
        "-i",
        "-L",
        "-l",
        "-P",
        "-s",
        "-a",
        "-d",
        "-E",
        "--max-args",
        "--replace",
        "--max-lines",
        "--max-procs",
        "--max-chars",
        "--arg-file",
        "--delimiter",
        "--eof",
    },
    "stdbuf": {"-i", "-o", "-e", "--input", "--output", "--error"},
    "unbuffer": set(),
    "caffeinate": {"-t", "-w"},
    "setsid": set(),
    "chrt": {"-p"},
}
WRAPPERS = set(WRAPPER_OPTION_ARGS)
SHELLS = {"sh", "bash", "zsh", "dash", "ksh", "ash", "fish"}
SHELL_OPTION_ARGS = {"-o", "+o", "--rcfile", "--init-file", "-O", "+O"}
MAX_SHELL_DEPTH = 3
ROOT_PATHSPECS = {".", "./", ":/", ":(top)", "*", ":", "./*", "../", ".."}
SUBSTITUTION_RE = re.compile(r"\$\(|`|<\(|__SUBST__")
SUBST_PLACEHOLDER = "__SUBST__"
REDIRECT_TOKENS = {"<", ">", ">>", "<<", "<<<", ">&", "<&", "&>", "&>>", ">|"}
ENV_ASSIGN_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*=")
HEREDOC_RE = re.compile(r"<<-?\s*(?P<q>['\"]?)(?P<tag>[A-Za-z_][A-Za-z0-9_]*)(?P=q)")

GIT_GLOBAL_WITH_ARG = {
    "-C",
    "-c",
    "--git-dir",
    "--work-tree",
    "--namespace",
    "--exec-path",
    "--super-prefix",
}
GIT_GLOBAL_FLAGS = {
    "--no-pager",
    "-p",
    "--paginate",
    "--no-optional-locks",
    "--literal-pathspecs",
    "--glob-pathspecs",
    "--noglob-pathspecs",
    "--icase-pathspecs",
    "--no-replace-objects",
    "--bare",
    "--html-path",
    "--man-path",
    "--info-path",
}

HOOK_OVERRIDE_RE = re.compile(
    r"^(core\.hookspath|include\.path|includeif\.|core\.fsmonitor|alias\.)", re.IGNORECASE
)
# Programs whose arguments are files they read, copy or send.
SECRET_READERS = {
    "cat",
    "less",
    "more",
    "head",
    "tail",
    "bat",
    "strings",
    "xxd",
    "hexdump",
    "base64",
    "cp",
    "scp",
    "rsync",
    "curl",
    "wget",
    "open",
    "pbcopy",
    "xclip",
    "source",
    ".",
}
# A file that holds credentials by name. Matched on the tail of a path, also after @ (curl -d @.env).
SECRET_FILE_RE = re.compile(
    r"(^|[/@])(\.env(\.[\w.-]+)?|\.netrc|\.npmrc|\.pypirc|\.git-credentials"
    r"|id_(rsa|dsa|ecdsa|ed25519)(\.pub)?|credentials(\.json)?|service[-_]?account[\w.-]*\.json"
    r"|[\w.-]+\.(pem|key|p12|pfx|jks|keystore|kdbx))\*?$"
)
COPY_PROGRAMS = {"cp", "scp", "rsync"}
SECRET_FILE_EXAMPLE_RE = re.compile(r"\.(example|sample|template|dist|md|txt)$", re.IGNORECASE)
CONFIG_READ_FORMS = {
    "--get",
    "--get-all",
    "--get-regexp",
    "--unset",
    "--unset-all",
    "--list",
    "-l",
    "get",
    "unset",
    "list",
}

GH_WRITE: dict[str, set[str]] = {
    "pr": {
        "create",
        "edit",
        "merge",
        "close",
        "reopen",
        "comment",
        "review",
        "ready",
        "lock",
        "unlock",
        "update-branch",
    },
    "issue": {
        "create",
        "edit",
        "close",
        "reopen",
        "comment",
        "delete",
        "transfer",
        "pin",
        "unpin",
        "lock",
        "unlock",
        "develop",
    },
    "release": {"create", "edit", "delete", "delete-asset", "upload"},
    "repo": {"create", "delete", "edit", "rename", "archive", "unarchive", "sync", "fork"},
    "label": {"create", "edit", "delete", "clone"},
    "workflow": {"run", "enable", "disable"},
    "run": {"rerun", "cancel", "delete"},
    "gist": {"create", "edit", "delete", "rename"},
    "secret": {"set", "delete"},
    "variable": {"set", "delete"},
    "project": {
        "create",
        "edit",
        "delete",
        "close",
        "copy",
        "item-add",
        "item-create",
        "item-edit",
        "item-delete",
        "item-archive",
        "link",
        "unlink",
        "field-create",
        "field-delete",
        "mark-template",
    },
    "codespace": {"create", "delete", "edit", "rebuild", "stop"},
    "ssh-key": {"add", "delete"},
    "gpg-key": {"add", "delete"},
    "cache": {"delete"},
}
GLAB_WRITE: dict[str, set[str]] = {
    "mr": {
        "create",
        "update",
        "merge",
        "approve",
        "revoke",
        "close",
        "reopen",
        "note",
        "comment",
        "rebase",
        "todo",
        "subscribe",
        "unsubscribe",
        "delete",
    },
    "issue": {
        "create",
        "update",
        "close",
        "reopen",
        "note",
        "comment",
        "delete",
        "subscribe",
        "unsubscribe",
        "link",
        "unlink",
        "board",
    },
    "release": {"create", "upload", "delete", "delete-asset"},
    "repo": {"create", "delete", "archive", "unarchive", "fork", "transfer", "mirror"},
    "label": {"create", "delete"},
    "ci": {"run", "retry", "cancel", "delete", "trigger"},
    "variable": {"set", "update", "delete", "create"},
    "snippet": {"create", "delete"},
    "schedule": {"create", "run", "delete", "update"},
    "ssh-key": {"add", "delete"},
}
GH_TEXT_OPTIONS = {"--body", "-b", "--title", "-t", "--notes", "-n", "--comment", "-c", "--subject"}
GH_TEXT_FILE_OPTIONS = {"--body-file", "-F", "--notes-file", "--input"}
GLAB_TEXT_OPTIONS = {
    "--description",
    "-d",
    "--title",
    "-t",
    "--message",
    "-m",
    "--note",
    "--notes",
    "-n",
}
GLAB_TEXT_FILE_OPTIONS = {"--description-file", "--notes-file", "--input"}
API_FIELD_OPTIONS = {"-f", "--raw-field", "-F", "--field"}


@dataclass
class Facts:
    tokens: list[str]
    kind: str = "other"
    add_all: bool = False
    commit_all: bool = False
    amend: bool = False
    dry_run: bool = False
    texts: list[str] = field(default_factory=list)
    text_files: list[str] = field(default_factory=list)
    text_from_stdin: bool = False
    force: bool = False
    force_tags: bool = False
    mirror: bool = False
    deletes: list[str] = field(default_factory=list)
    targets: list[str] = field(default_factory=list)
    tags_pushed: bool = False
    post: bool = False
    post_reason: str = ""
    workdir: Path | None = None
    text_by_substitution: bool = False
    text_file_missing: bool = False
    no_verify: bool = False
    hooks_path_override: bool = False
    reads_secret_file: list[str] = field(default_factory=list)

    @property
    def is_commit(self) -> bool:
        return self.kind == "git-commit"

    @property
    def is_push(self) -> bool:
        return self.kind == "git-push"

    @property
    def carries_text(self) -> bool:
        return self.kind in ("git-commit", "git-tag") or self.post


@dataclass
class Parsed:
    raw: str
    commands: list[Facts]
    heredocs: list[str]

    @property
    def gated(self) -> bool:
        return any(c.is_commit or c.is_push or c.post for c in self.commands)

    @property
    def traced(self) -> bool:
        """True when at least one simple command was recognised as git, gh or glab."""
        return any(c.kind != "other" for c in self.commands)


def split_heredocs(raw: str) -> tuple[str, list[str]]:
    """Return the command text with heredoc bodies removed, and the bodies."""
    lines = raw.split("\n")
    kept: list[str] = []
    bodies: list[str] = []
    index = 0
    while index < len(lines):
        line = lines[index]
        kept.append(line)
        tags = [(m.group("tag"), "<<-" in m.group(0)) for m in HEREDOC_RE.finditer(line)]
        index += 1
        for tag, strip_tabs in tags:
            body: list[str] = []
            while index < len(lines):
                candidate = lines[index]
                index += 1
                check = candidate.lstrip("\t") if strip_tabs else candidate
                if check == tag:
                    break
                body.append(candidate)
            bodies.append("\n".join(body))
    return "\n".join(kept), bodies


def _mark_newlines(text: str) -> str:
    """Turn every newline outside quotes into a ``;`` separator and join backslash
    continuations, so a multi-line message inside quotes stays one token."""
    out: list[str] = []
    quote: str | None = None
    index = 0
    length = len(text)
    while index < length:
        ch = text[index]
        if quote == "'":
            out.append(ch)
            if ch == "'":
                quote = None
            index += 1
            continue
        if ch == "\\" and index + 1 < length:
            nxt = text[index + 1]
            if nxt == "\n" and quote is None:
                index += 2
                continue
            out.append(ch)
            out.append(nxt)
            index += 2
            continue
        if quote == '"':
            out.append(ch)
            if ch == '"':
                quote = None
            index += 1
            continue
        if ch in ("'", '"'):
            quote = ch
        elif ch == "\n":
            out.append(" ; ")
            index += 1
            continue
        out.append(ch)
        index += 1
    return "".join(out)


def mask_substitutions(text: str) -> str:
    """Replace command and process substitutions outside single quotes with a placeholder,
    so ``$( … )``, ``<( … )`` and backticks neither split the command nor pass as text."""
    out: list[str] = []
    index = 0
    length = len(text)
    in_single = False
    while index < length:
        ch = text[index]
        if in_single:
            out.append(ch)
            if ch == "'":
                in_single = False
            index += 1
            continue
        if ch == "\\" and index + 1 < length:
            out.append(ch)
            out.append(text[index + 1])
            index += 2
            continue
        if ch == "'":
            in_single = True
            out.append(ch)
            index += 1
            continue
        if ch == "`":
            end = text.find("`", index + 1)
            if end == -1:
                out.append(ch)
                index += 1
                continue
            out.append(SUBST_PLACEHOLDER)
            index = end + 1
            continue
        if text.startswith(("$(", "<(", ">("), index):
            depth = 0
            scan = index + 1
            while scan < length:
                if text[scan] == "(":
                    depth += 1
                elif text[scan] == ")":
                    depth -= 1
                    if depth == 0:
                        break
                scan += 1
            if scan >= length:
                out.append(ch)
                index += 1
                continue
            out.append(SUBST_PLACEHOLDER)
            index = scan + 1
            continue
        out.append(ch)
        index += 1
    return "".join(out)


def _strip_redirections(tokens: list[str]) -> list[str]:
    """Drop redirection operators, their file operands and a file-descriptor digit before them."""
    out: list[str] = []
    skip_next = False
    for token in tokens:
        if skip_next:
            skip_next = False
            continue
        if token in REDIRECT_TOKENS:
            if out and out[-1].isdigit() and len(out[-1]) == 1:
                out.pop()
            skip_next = token not in (">&", "<&") or True
            continue
        out.append(token)
    return out


def tokenize(line: str) -> list[str]:
    lexer = shlex.shlex(line, posix=True, punctuation_chars=True)
    lexer.whitespace_split = True
    lexer.commenters = ""
    try:
        return list(lexer)
    except ValueError:
        return line.split()


def simple_commands(text: str) -> list[list[str]]:
    """Token lists for each simple command in ``text`` (heredoc bodies already removed)."""
    out: list[list[str]] = []
    current: list[str] = []
    for token in tokenize(_mark_newlines(text)):
        if token in OPERATORS:
            if current:
                out.append(current)
            current = []
        else:
            current.append(token)
    if current:
        out.append(current)
    return out


def _strip_wrappers(tokens: list[str]) -> list[str]:
    """Drop variable assignments and wrapper programs (with their options) from the front."""
    rest = list(tokens)
    hops = 0
    while rest and hops < 8:
        head = rest[0]
        if ENV_ASSIGN_RE.match(head):
            rest.pop(0)
            continue
        name = _basename(head)
        if name == "command" and len(rest) > 1 and rest[1] in ("-v", "-V"):
            break
        if name not in WRAPPERS:
            break
        rest.pop(0)
        hops += 1
        with_arg = WRAPPER_OPTION_ARGS[name]
        while rest:
            token = rest[0]
            if token == "--":
                rest.pop(0)
                break
            if token.startswith("-") and len(token) > 1:
                rest.pop(0)
                if token in with_arg and rest:
                    rest.pop(0)
                continue
            break
        if name == "timeout" and rest:
            rest.pop(0)
    return rest


def shell_inner(tokens: list[str]) -> str | None:
    """The command string a shell wrapper or ``eval`` would run, or None."""
    rest = _strip_wrappers(tokens)
    if not rest:
        return None
    name = _basename(rest[0])
    if name == "eval":
        return " ".join(rest[1:]) or None
    if name not in SHELLS:
        return None
    index = 1
    while index < len(rest):
        token = rest[index]
        if token == "--":
            return None
        if token in SHELL_OPTION_ARGS:
            index += 2
            continue
        if token.startswith("--"):
            index += 1
            continue
        if token.startswith(("-", "+")) and len(token) > 1:
            if "c" in token[1:]:
                return rest[index + 1] if index + 1 < len(rest) else None
            index += 1
            continue
        return None
    return None


def _expand(token_lists: list[list[str]], depth: int = 0) -> list[list[str]]:
    out: list[list[str]] = []
    for tokens in token_lists:
        inner = shell_inner(tokens) if depth < MAX_SHELL_DEPTH else None
        if inner is None:
            out.append(tokens)
        else:
            out.extend(_expand(simple_commands(inner), depth + 1))
    return out


def _basename(token: str) -> str:
    return token.rsplit("/", 1)[-1]


def _short_flags(token: str) -> str:
    """Letters of a combined short-flag token such as ``-am``; empty for anything else."""
    if token.startswith("-") and not token.startswith("--") and len(token) > 1:
        return token[1:]
    return ""


def parse(raw: str, cwd: Path | None = None, extra_posting: Iterable[str] = ()) -> Parsed:
    text, heredocs = split_heredocs(raw)
    text = mask_substitutions(text)
    commands: list[Facts] = []
    current = cwd
    for tokens in _expand(simple_commands(text)):
        stripped = _strip_wrappers(tokens)
        if stripped and stripped[0] in ("cd", "pushd"):
            current = _resolve(current, stripped[1]) if len(stripped) > 1 else current
            commands.append(Facts(tokens=list(tokens)))
            continue
        commands.append(classify(tokens, current, extra_posting))
    return Parsed(raw=raw, commands=commands, heredocs=heredocs)


def _resolve(base: Path | None, value: str) -> Path | None:
    if value in ("-", "~", "$HOME") or value.startswith(("$", "~")):
        return None
    path = Path(value)
    if path.is_absolute():
        return path
    return (base / path) if base is not None else None


def classify(
    tokens: list[str], cwd: Path | None = None, extra_posting: Iterable[str] = ()
) -> Facts:
    facts = Facts(tokens=list(tokens), workdir=cwd)
    rest = _strip_wrappers(_strip_redirections(tokens))
    if not rest:
        return facts
    program = _basename(rest[0])
    args = rest[1:]
    if program == "git":
        facts.workdir = _git_workdir(args, cwd)
        facts.hooks_path_override = _overrides_hooks(args)
        _classify_git(facts, args, facts.workdir)
    elif program in SECRET_READERS:
        facts.kind = "read"
        operands = [a for a in args if not a.startswith("-")]
        if program in COPY_PROGRAMS:
            operands = operands[:-1]  # the last operand is the destination, a write
        facts.reads_secret_file = [a for a in operands if is_secret_file(a)]
    elif program == "gh":
        _classify_gh(facts, args)
    elif program == "glab":
        _classify_glab(facts, args)
    joined = " ".join(rest)
    for pattern in extra_posting:
        try:
            if re.search(pattern, joined):
                facts.post = True
                facts.post_reason = (
                    facts.post_reason or f"matches posting.extra_commands {pattern!r}"
                )
        except re.error:
            continue
    return facts


def is_secret_file(path: str) -> bool:
    """True when the path names a credential file and is not a published example of one."""
    return bool(SECRET_FILE_RE.search(path)) and not SECRET_FILE_EXAMPLE_RE.search(path)


def _config_sets_hooks(rest: list[str]) -> bool:
    """True for ``git config [--global] core.hooksPath <value>`` and the other keys that change
    which hooks run; reading or unsetting the key is not an override."""
    if any(token in CONFIG_READ_FORMS for token in rest):
        return False
    for index, token in enumerate(rest):
        if HOOK_OVERRIDE_RE.match(token) and index + 1 < len(rest):
            return True
    return False


def _git_globals(args: list[str]) -> tuple[list[tuple[str, str]], int]:
    """Global options before the git subcommand as (option, value) pairs, and the index of the
    subcommand (``len(args)`` when there is none). ``-cKEY=VAL``, ``--git-dir=X`` and the
    two-token forms come back as pairs; a flag comes back with an empty value."""
    pairs: list[tuple[str, str]] = []
    index = 0
    while index < len(args):
        token = args[index]
        if token in GIT_GLOBAL_WITH_ARG:
            pairs.append((token, args[index + 1] if index + 1 < len(args) else ""))
            index += 2
            continue
        if (
            token.startswith("--")
            and "=" in token
            and token.split("=", 1)[0] in GIT_GLOBAL_WITH_ARG
        ):
            option, value = token.split("=", 1)
            pairs.append((option, value))
            index += 1
            continue
        if token.startswith("-c") and len(token) > 2 and not token.startswith("--"):
            pairs.append(("-c", token[2:]))
            index += 1
            continue
        if token.startswith("-"):
            pairs.append((token, ""))
            index += 1
            continue
        break
    return pairs, index


def _overrides_hooks(args: list[str]) -> bool:
    """True when a global -c sets core.hooksPath, include.path or an alias on the command line."""
    pairs, _ = _git_globals(args)
    return any(option == "-c" and HOOK_OVERRIDE_RE.match(value) for option, value in pairs)


def _git_workdir(args: list[str], cwd: Path | None) -> Path | None:
    """The directory a git command runs in after its global ``-C`` options."""
    current = cwd
    for option, value in _git_globals(args)[0]:
        if option == "-C" and value:
            current = _resolve(current, value)
    return current


def _git_subcommand(args: list[str]) -> tuple[str | None, list[str]]:
    _, index = _git_globals(args)
    if index >= len(args):
        return None, []
    return args[index], args[index + 1 :]


def _classify_git(facts: Facts, args: list[str], cwd: Path | None) -> None:
    sub, rest = _git_subcommand(args)
    if sub is None:
        facts.kind = "git-other"
        return
    if sub == "add":
        facts.kind = "git-add"
        _parse_add(facts, rest)
    elif sub == "commit":
        facts.kind = "git-commit"
        _parse_commit(facts, rest)
    elif sub == "push":
        facts.kind = "git-push"
        _parse_push(facts, rest, cwd)
    elif sub == "tag":
        facts.kind = "git-tag"
        _parse_tag(facts, rest)
    elif sub == "config":
        facts.kind = "git-config"
        facts.hooks_path_override = facts.hooks_path_override or _config_sets_hooks(rest)
    else:
        facts.kind = "git-other"


def _parse_add(facts: Facts, rest: list[str]) -> None:
    pathspecs: list[str] = []
    update = False
    seen_dashdash = False
    for token in rest:
        if seen_dashdash:
            pathspecs.append(token)
            continue
        if token == "--":
            seen_dashdash = True
            continue
        if token in ("-A", "--all", "--no-ignore-removal"):
            facts.add_all = True
        elif token in ("-u", "--update"):
            update = True
        elif token.startswith("--"):
            continue
        elif flags := _short_flags(token):
            if "A" in flags:
                facts.add_all = True
            if "u" in flags:
                update = True
        else:
            pathspecs.append(token)
    narrowing = [spec for spec in pathspecs if spec not in ROOT_PATHSPECS]
    root_like = [spec for spec in pathspecs if spec in ROOT_PATHSPECS]
    if root_like:
        facts.add_all = True
    elif (facts.add_all or update) and narrowing:
        facts.add_all = False
    elif update and not pathspecs:
        facts.add_all = True


COMMIT_ARG_LETTERS = set("mFCctoS")


def _parse_commit(facts: Facts, rest: list[str]) -> None:
    index = 0
    while index < len(rest):
        token = rest[index]
        index += 1
        if token == "--":
            break
        if token in ("-a", "--all"):
            facts.commit_all = True
        elif token == "--amend":
            facts.amend = True
        elif token == "--dry-run":
            facts.dry_run = True
        elif token in ("-n", "--no-verify"):
            facts.no_verify = True
        elif token in ("-m", "--message"):
            if index < len(rest):
                facts.texts.append(rest[index])
                index += 1
        elif token.startswith("--message="):
            facts.texts.append(token.split("=", 1)[1])
        elif token in ("-F", "--file"):
            if index < len(rest):
                _text_file(facts, rest[index])
                index += 1
        elif token.startswith("--file="):
            _text_file(facts, token.split("=", 1)[1])
        elif token == "--trailer":
            if index < len(rest):
                facts.texts.append(rest[index])
                index += 1
        elif token.startswith("--trailer="):
            facts.texts.append(token.split("=", 1)[1])
        elif token.startswith("--"):
            if "=" not in token and token in (
                "--template",
                "--reuse-message",
                "--reedit-message",
                "--fixup",
                "--squash",
                "--author",
                "--date",
                "--cleanup",
                "--gpg-sign",
                "--pathspec-from-file",
                "--only",
            ):
                index += 1
        else:
            flags = _short_flags(token)
            if not flags:
                continue
            for position, letter in enumerate(flags):
                if letter == "a":
                    facts.commit_all = True
                elif letter == "n":
                    facts.no_verify = True
                elif letter in COMMIT_ARG_LETTERS:
                    attached = flags[position + 1 :]
                    if attached:
                        value = attached
                    elif index < len(rest):
                        value = rest[index]
                        index += 1
                    else:
                        value = ""
                    if letter == "m":
                        facts.texts.append(value)
                    elif letter == "F":
                        _text_file(facts, value)
                    break


def _text_file(facts: Facts, value: str) -> None:
    if value in ("-", "/dev/stdin"):
        facts.text_from_stdin = True
    elif value.startswith("<(") or SUBST_PLACEHOLDER in value:
        facts.text_by_substitution = True
    elif value:
        facts.text_files.append(value)


def _parse_tag(facts: Facts, rest: list[str]) -> None:
    index = 0
    while index < len(rest):
        token = rest[index]
        index += 1
        if token in ("-m", "--message") and index < len(rest):
            facts.texts.append(rest[index])
            index += 1
        elif token.startswith("--message="):
            facts.texts.append(token.split("=", 1)[1])
        elif token in ("-F", "--file") and index < len(rest):
            _text_file(facts, rest[index])
            index += 1
        elif token.startswith("--file="):
            _text_file(facts, token.split("=", 1)[1])
        elif token in ("-f", "--force"):
            facts.force = True
        else:
            flags = _short_flags(token)
            if "f" in flags:
                facts.force = True
            if "m" in flags:
                attached = flags.split("m", 1)[1]
                if attached:
                    facts.texts.append(attached)
                elif index < len(rest):
                    facts.texts.append(rest[index])
                    index += 1


PUSH_WITH_ARG = {
    "-o",
    "--push-option",
    "--repo",
    "--receive-pack",
    "--exec",
    "--signed",
    "--recurse-submodules",
}


def _parse_push(facts: Facts, rest: list[str], cwd: Path | None) -> None:
    positionals: list[str] = []
    index = 0
    delete = False
    push_all = False
    while index < len(rest):
        token = rest[index]
        index += 1
        if token == "--":
            positionals.extend(rest[index:])
            break
        if (
            token in ("-f", "--force")
            or token.startswith("--force-with-lease")
            or token == "--force-if-includes"
        ):
            facts.force = True
        elif token == "--tags":
            facts.tags_pushed = True
        elif token in ("--all", "--branches"):
            push_all = True
        elif token == "--mirror":
            facts.mirror = True
            facts.force = True
        elif token in ("-d", "--delete"):
            delete = True
        elif token in ("-n", "--dry-run"):
            facts.dry_run = True
        elif token == "--no-verify":
            facts.no_verify = True
        elif token in PUSH_WITH_ARG:
            index += 1
        elif token.startswith("--"):
            continue
        elif flags := _short_flags(token):
            if "f" in flags:
                facts.force = True
            if "d" in flags:
                delete = True
            if "n" in flags:
                facts.dry_run = True
            if "o" in flags:
                index += 1
        else:
            positionals.append(token)
    refspecs = positionals[1:] if positionals else []
    if delete:
        facts.deletes = [_branch_name(r) for r in refspecs]
        return
    explicit = False
    for spec in refspecs:
        explicit = True
        force_this = spec.startswith("+")
        spec = spec.lstrip("+")
        if ":" in spec:
            src, dst = spec.split(":", 1)
        else:
            src, dst = spec, spec
        if src == "":
            facts.deletes.append(_branch_name(dst))
            continue
        if _looks_like_tag(src, dst, cwd):
            facts.tags_pushed = True
            if force_this or facts.force:
                facts.force_tags = True
            continue
        if force_this:
            facts.force = True
        name = _branch_name(dst)
        if name == "HEAD":
            name = current_branch(cwd) or "HEAD"
        facts.targets.append(name)
    if facts.tags_pushed and facts.force:
        facts.force_tags = True
    if push_all or facts.mirror:
        facts.targets.append("*")
    if not explicit and not facts.tags_pushed and not push_all and not facts.mirror:
        facts.targets.append(current_branch(cwd) or "HEAD")


def _branch_name(ref: str) -> str:
    for prefix in ("refs/heads/", "refs/remotes/origin/", "heads/"):
        if ref.startswith(prefix):
            return ref[len(prefix) :]
    return ref


def _looks_like_tag(src: str, dst: str, cwd: Path | None) -> bool:
    if src.startswith("refs/tags/") or dst.startswith("refs/tags/") or src.startswith("tags/"):
        return True
    if dst.startswith("refs/heads/") or src in ("HEAD",):
        return False
    if cwd is not None and src and not src.startswith("refs/"):
        return ref_is_tag(cwd, src)
    return False


def current_branch(cwd: Path | None) -> str | None:
    if cwd is None:
        return None
    out = _git(cwd, "symbolic-ref", "--short", "-q", "HEAD")
    return out or None


def ref_is_tag(cwd: Path, name: str) -> bool:
    try:
        result = subprocess.run(
            ["git", "-C", str(cwd), "show-ref", "--verify", "--quiet", f"refs/tags/{name}"],
            capture_output=True,
            timeout=3,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return False
    return result.returncode == 0


def _git(cwd: Path, *args: str) -> str:
    try:
        result = subprocess.run(
            ["git", "-C", str(cwd), *args], capture_output=True, text=True, timeout=3, check=False
        )
    except (OSError, subprocess.SubprocessError):
        return ""
    return result.stdout.strip() if result.returncode == 0 else ""


def _collect_text_options(
    facts: Facts, args: list[str], text_options: set[str], file_options: set[str], api: bool = False
) -> None:
    index = 0
    while index < len(args):
        token = args[index]
        index += 1
        name, _, inline = token.partition("=")
        has_inline = "=" in token and token.startswith("--")
        if api and name in API_FIELD_OPTIONS:
            value = args[index] if index < len(args) else ""
            index += 1
            if value:
                facts.texts.append(value.split("=", 1)[1] if "=" in value else value)
        elif api and name == "--input":
            value = inline if has_inline else (args[index] if index < len(args) else "")
            if not has_inline:
                index += 1
            _text_file(facts, value)
        elif not api and name in text_options:
            value = inline if has_inline else (args[index] if index < len(args) else "")
            if not has_inline:
                index += 1
            if value:
                facts.texts.append(value)
        elif not api and name in file_options:
            value = inline if has_inline else (args[index] if index < len(args) else "")
            if not has_inline:
                index += 1
            _text_file(facts, value)


def _classify_gh(facts: Facts, args: list[str]) -> None:
    facts.kind = "gh"
    if not args:
        return
    group = args[0]
    if group == "api":
        method = "GET"
        has_fields = False
        index = 1
        while index < len(args):
            token = args[index]
            index += 1
            if token in ("-X", "--method") and index < len(args):
                method = args[index].upper()
                index += 1
            elif token.startswith("--method="):
                method = token.split("=", 1)[1].upper()
            elif token in API_FIELD_OPTIONS or token == "--input":
                has_fields = True
        if method != "GET" or has_fields:
            facts.post = True
            facts.post_reason = f"gh api {method if method != 'GET' else 'POST'}"
            _collect_text_options(facts, args[1:], set(), set(), api=True)
        return
    verb = args[1] if len(args) > 1 else ""
    if verb in GH_WRITE.get(group, set()):
        facts.post = True
        facts.post_reason = f"gh {group} {verb}"
        _collect_text_options(facts, args[2:], GH_TEXT_OPTIONS, GH_TEXT_FILE_OPTIONS)


def _classify_glab(facts: Facts, args: list[str]) -> None:
    facts.kind = "glab"
    if not args:
        return
    group = args[0]
    if group == "api":
        method = "GET"
        index = 1
        has_fields = False
        while index < len(args):
            token = args[index]
            index += 1
            if token in ("-X", "--method") and index < len(args):
                method = args[index].upper()
                index += 1
            elif token.startswith("--method="):
                method = token.split("=", 1)[1].upper()
            elif token in ("-f", "--field", "-F", "--raw-field", "--input"):
                has_fields = True
        if method != "GET" or has_fields:
            facts.post = True
            facts.post_reason = f"glab api {method if method != 'GET' else 'POST'}"
            _collect_text_options(facts, args[1:], set(), set(), api=True)
        return
    verb = args[1] if len(args) > 1 else ""
    if verb in GLAB_WRITE.get(group, set()):
        facts.post = True
        facts.post_reason = f"glab {group} {verb}"
        _collect_text_options(facts, args[2:], GLAB_TEXT_OPTIONS, GLAB_TEXT_FILE_OPTIONS)


MAX_TEXT_FILE_BYTES = 1_000_000


def carried_text(parsed: Parsed, cwd: Path | None) -> str:
    """Every piece of change text the command carries: inline messages, referenced files that
    already exist, heredoc bodies, and the raw command when a message comes from stdin."""
    pieces: list[str] = []
    stdin_used = False
    file_missing = False
    for facts in parsed.commands:
        if not facts.carries_text:
            continue
        for piece in facts.texts:
            pieces.append(piece)
            if "\\n" in piece:
                pieces.append(piece.replace("\\n", "\n"))
            if SUBSTITUTION_RE.search(piece):
                facts.text_by_substitution = True
        if facts.text_from_stdin:
            stdin_used = True
        for name in facts.text_files:
            path = Path(name)
            base = facts.workdir or cwd
            if not path.is_absolute() and base is not None:
                path = base / path
            try:
                if path.is_file() and path.stat().st_size <= MAX_TEXT_FILE_BYTES:
                    pieces.append(path.read_text(encoding="utf-8", errors="replace"))
                    continue
            except OSError:
                pass
            facts.text_file_missing = True  # written by this command, or absent: scan the raw text
            file_missing = True
    if parsed.heredocs and (stdin_used or any(f.carries_text for f in parsed.commands)):
        pieces.extend(parsed.heredocs)
    if stdin_used or file_missing:
        pieces.append(parsed.raw)
        if "\\n" in parsed.raw:
            pieces.append(parsed.raw.replace("\\n", "\n"))
    return "\n".join(pieces)
