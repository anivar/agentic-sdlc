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

OPERATORS = {"&&", "||", ";", ";;", "|", "|&", "&"}
WRAPPERS = {"command", "exec", "nohup", "nice", "time", "sudo", "env", "builtin"}
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
    rest = list(tokens)
    while rest:
        head = rest[0]
        if ENV_ASSIGN_RE.match(head) or head in WRAPPERS:
            rest.pop(0)
            if head == "sudo":
                while rest and rest[0].startswith("-"):
                    rest.pop(0)
            continue
        if head == "timeout":
            rest = rest[2:]
            continue
        break
    return rest


def _basename(token: str) -> str:
    return token.rsplit("/", 1)[-1]


def _short_flags(token: str) -> str:
    """Letters of a combined short-flag token such as ``-am``; empty for anything else."""
    if token.startswith("-") and not token.startswith("--") and len(token) > 1:
        return token[1:]
    return ""


def parse(raw: str, cwd: Path | None = None, extra_posting: Iterable[str] = ()) -> Parsed:
    text, heredocs = split_heredocs(raw)
    commands = [classify(tokens, cwd, extra_posting) for tokens in simple_commands(text)]
    return Parsed(raw=raw, commands=commands, heredocs=heredocs)


def classify(
    tokens: list[str], cwd: Path | None = None, extra_posting: Iterable[str] = ()
) -> Facts:
    facts = Facts(tokens=list(tokens))
    rest = _strip_wrappers(tokens)
    if not rest:
        return facts
    program = _basename(rest[0])
    args = rest[1:]
    if program == "git":
        _classify_git(facts, args, cwd)
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


def _git_subcommand(args: list[str]) -> tuple[str | None, list[str]]:
    index = 0
    while index < len(args):
        token = args[index]
        if token in GIT_GLOBAL_WITH_ARG:
            index += 2
            continue
        if (
            token.startswith("--")
            and "=" in token
            and token.split("=", 1)[0] in GIT_GLOBAL_WITH_ARG
        ):
            index += 1
            continue
        if token in GIT_GLOBAL_FLAGS:
            index += 1
            continue
        if token.startswith("-"):
            index += 1
            continue
        return token, args[index + 1 :]
    return None, []


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
    if update and not pathspecs:
        facts.add_all = True
    for spec in pathspecs:
        if spec in (".", "./", ":/", ":(top)", "*", ":", "./*"):
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
        elif token in ("--dry-run", "-n"):
            facts.dry_run = True
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
                "--trailer",
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
                    facts.dry_run = True
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
            timeout=5,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return False
    return result.returncode == 0


def _git(cwd: Path, *args: str) -> str:
    try:
        result = subprocess.run(
            ["git", "-C", str(cwd), *args], capture_output=True, text=True, timeout=5, check=False
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
    for facts in parsed.commands:
        if not facts.carries_text:
            continue
        pieces.extend(facts.texts)
        if facts.text_from_stdin:
            stdin_used = True
        for name in facts.text_files:
            path = Path(name)
            if not path.is_absolute() and cwd is not None:
                path = cwd / path
            try:
                if path.is_file() and path.stat().st_size <= MAX_TEXT_FILE_BYTES:
                    pieces.append(path.read_text(encoding="utf-8", errors="replace"))
            except OSError:
                continue
    if parsed.heredocs and (stdin_used or any(f.carries_text for f in parsed.commands)):
        pieces.extend(parsed.heredocs)
    if stdin_used:
        pieces.append(parsed.raw)
    return "\n".join(pieces)
