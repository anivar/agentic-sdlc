"""Shell command analysis for the git and forge rules.

A Bash tool call carries one string that may hold several simple commands joined by
``&&``, ``||``, ``;``, pipes and newlines, plus heredocs. This module splits it, classifies
each simple command and extracts the change text it carries (commit messages, PR bodies,
issue text, release notes) so the text rules can run before anything is sent.

The parser is deliberately tolerant: it never raises on odd input, and when it cannot
tell, it reports what it saw and lets ``guard`` decide conservatively.
"""

from __future__ import annotations

import os
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
# A here-string (``<<<``) is not a heredoc: it reads no lines after the command.
HEREDOC_RE = re.compile(r"(?<!<)<<(?!<)-?\s*(?P<q>['\"]?)(?P<tag>[A-Za-z_][A-Za-z0-9_]*)(?P=q)")

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
# Programs beyond SECRET_READERS that print, compare, archive or send a file named on their
# command line. They count for SECRET-3 only: their kind stays "other", so a search is never
# mistaken for a traced git call.
SECRET_PRINTERS = {
    "grep",
    "egrep",
    "fgrep",
    "rg",
    "ag",
    "awk",
    "gawk",
    "sed",
    "gsed",
    "sort",
    "uniq",
    "nl",
    "od",
    "tac",
    "rev",
    "cut",
    "paste",
    "column",
    "jq",
    "yq",
    "diff",
    "cmp",
    "openssl",
    "gpg",
    "zcat",
    "tar",
    "zip",
}
# Files whose change alters what the guard does (GUARD-2), matched on the path's tail. The git
# configuration files are here because a hooksPath set in one switches the git hooks off, and
# the Codex files because they hold its hooks and the switch that turns hooks off.
GUARD_CONFIG_RE = re.compile(
    r"(^|/)(\.agentic-sdlc\.json|\.pre-commit-config\.yaml|\.claude/settings(\.local)?\.json"
    r"|\.git/hooks(/[^/]+)?|hooks/hooks\.json|\.codex/(config\.toml|hooks\.json)"
    r"|\.git/config|\.gitconfig|\.config/git/config)/?$"
)
# Programs that change or remove every file named on their command line (GUARD-2).
FILE_CHANGERS = {
    "tee",
    "rm",
    "unlink",
    "truncate",
    "shred",
    "chmod",
    "chown",
    "chgrp",
    "mv",
    "sponge",
}
# Programs whose last operand is the file they write.
FILE_COPIERS = {"cp", "install", "ln", "rsync", "scp", "ditto"}
# Programs that edit their file operands in place when given -i.
IN_PLACE_EDITORS = {"sed", "gsed", "perl"}
# Redirections that write their target. The target of >& is a file only when it is not a
# descriptor digit or "-".
OUTPUT_REDIRECTS = {">", ">>", ">|", "&>", "&>>", ">&"}
# Interpreters that run code given on their command line, and the short flags that take it.
# Python's flag is -c; deno takes its code after the eval subcommand.
PYTHON_RE = re.compile(r"^(python|pypy)[0-9.]*$")
INLINE_CODE_FLAGS = {
    "node": "ep",
    "nodejs": "ep",
    "ruby": "e",
    "perl": "eE",
    "php": "r",
    "bun": "e",
    "osascript": "e",
}
INLINE_CODE_LONG = {"--eval", "--print"}
# Words in inline code that could be a path: the parser cannot run the code, so any word that
# names a guarded or secret file counts.
PATHLIKE_RE = re.compile(r"[\w@.~/*+-]+")
# A variable reference in an argument; ${#NAME} is the length and prints no secret.
VAR_REF_RE = re.compile(r"\$\{?(?!#)([A-Za-z_][A-Za-z0-9_]*)")
# Code that names a guarded file changes it only when the code also writes something, so a
# read of the guard's configuration from inline code passes (GUARD-2).
CODE_WRITE_RE = re.compile(
    r"write|append|unlink|remove|rename|replace|truncate|chmod|copy|move|dump|rmdir|rmSync"
    r"|\brm\b|['\"][wax]b?\+?['\"]|>",
    re.IGNORECASE,
)
# Interpreters that run a script file named as their first operand. A shell's script is parsed
# as shell; any other script is read like inline code.
SHELLS = {"sh", "bash", "zsh", "dash", "ksh", "source", "."}
SCRIPT_RUNNERS = {"node", "nodejs", "ruby", "perl", "php", "bun", "deno", "osascript"}
SCRIPT_LIMIT = 256 * 1024
# Environment variables a database client takes its target from when the command names none
# (PROD-1).
CLIENT_TARGET_ENV = {
    "psql": ("PGHOST", "PGHOSTADDR", "PGSERVICE", "PGDATABASE"),
    "pg_restore": ("PGHOST", "PGHOSTADDR", "PGSERVICE", "PGDATABASE"),
    "mysql": ("MYSQL_HOST",),
    "mariadb": ("MYSQL_HOST",),
}
# Parts of a variable name that mark it as holding a credential (SECRET-2).
SECRET_NAME_PARTS = {
    "TOKEN",
    "SECRET",
    "SECRETS",
    "PASSWORD",
    "PASSWD",
    "PASS",
    "KEY",
    "APIKEY",
    "CREDENTIAL",
    "CREDENTIALS",
    "PAT",
    "DSN",
    "COOKIE",
}
SECRET_NAME_ENDINGS = ("TOKEN", "SECRET", "PASSWORD", "APIKEY")
# Database clients and the flags that carry an inline statement: short-flag letters, then long
# flags. A client without an entry is treated as able to write on every call (PROD-1).
QUERY_FLAGS = {
    "psql": ("c", ("--command",)),
    "mysql": ("e", ("--execute",)),
    "mariadb": ("e", ("--execute",)),
    "sqlcmd": ("Qq", ()),
    "mongosh": ("", ("--eval",)),
    "mongo": ("", ("--eval",)),
    "cqlsh": ("e", ("--execute",)),
    "clickhouse-client": ("q", ("--query",)),
    "clickhouse": ("q", ("--query",)),
}
# Flags that read statements from a file the hook does not open.
QUERY_FILE_FLAGS = {
    "psql": ("-f", "--file"),
    "sqlcmd": ("-i",),
    "cqlsh": ("-f", "--file"),
    "mongosh": ("-f", "--file"),
    "clickhouse-client": ("--queries-file",),
    "clickhouse": ("--queries-file",),
}
# Statement text that changes data, schema or grants, or runs a file (psql \i).
SQL_WRITE_RE = re.compile(
    r"\b(?:insert|update|delete|merge|upsert|drop|alter|truncate|create|grant|revoke|call|exec"
    r"|execute|vacuum|reindex|cluster|replace\s+into|load\s+data|refresh\s+materialized"
    r"|comment\s+on)\b"
    r"|\bcopy\b[\s\S]*?\bfrom\b"
    r"|\\(?:ir?|include(?:_relative)?)\b",
    re.IGNORECASE,
)
# A MongoDB shell method that writes.
MONGO_WRITE_RE = re.compile(
    r"\.(?:insert|update|delete|replace|remove|drop|bulkWrite|findOneAnd|findAndModify|rename"
    r"|createIndex|createCollection)\w*\s*\("
)
REDIS_WRITE_VERBS = {
    "set",
    "setex",
    "psetex",
    "setnx",
    "mset",
    "msetnx",
    "append",
    "del",
    "unlink",
    "getdel",
    "getset",
    "expire",
    "pexpire",
    "expireat",
    "persist",
    "rename",
    "renamenx",
    "incr",
    "incrby",
    "decr",
    "decrby",
    "hset",
    "hmset",
    "hdel",
    "hincrby",
    "lpush",
    "rpush",
    "lpop",
    "rpop",
    "lrem",
    "lset",
    "ltrim",
    "sadd",
    "srem",
    "spop",
    "zadd",
    "zrem",
    "zincrby",
    "xadd",
    "xdel",
    "xtrim",
    "flushall",
    "flushdb",
    "config",
    "eval",
    "evalsha",
    "script",
    "function",
    "fcall",
    "restore",
    "migrate",
    "move",
    "copy",
    "swapdb",
    "shutdown",
    "debug",
    "bgsave",
    "save",
    "replicaof",
    "slaveof",
}
REDIS_VALUE_FLAGS = {
    "-h",
    "-p",
    "-s",
    "-a",
    "-u",
    "-n",
    "-r",
    "-i",
    "-d",
    "--user",
    "--pass",
    "--cacert",
    "--cacertdir",
    "--cert",
    "--key",
    "--sni",
}
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
        "revert",
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
    "repo": {
        "create",
        "delete",
        "edit",
        "rename",
        "archive",
        "unarchive",
        "sync",
        "fork",
        "set-default",
    },
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
    "discussion": {"create", "comment", "edit"},
    "skill": {"publish"},
    "agent-task": {"create"},
}
# Verbs verified read-only against `gh <noun> --help` (gh 2.102.0), and nouns whose every
# verb is read-only. scripts/check_verb_tables.py watches the CLIs for verbs neither table
# knows.
GH_READ = {
    "view",
    "list",
    "status",
    "browse",
    "search",
    "diff",
    "checks",
    "watch",
    "help",
    "get",
    "download",
    "clone",
    "logs",
    "field-list",
    "item-list",
}
GH_READ_NOUNS = {"browse", "search", "status", "org", "ruleset", "licenses", "completion"}
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
        "for",
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
    "repo": {
        "create",
        "delete",
        "archive",
        "unarchive",
        "fork",
        "transfer",
        "mirror",
        "update",
        "publish",
        "members",
    },
    "label": {"create", "delete", "edit"},
    "ci": {"run", "retry", "cancel", "delete", "trigger", "run-trig"},
    "variable": {"set", "update", "delete", "create", "import"},
    "snippet": {"create", "delete"},
    "schedule": {"create", "run", "delete", "update"},
    "ssh-key": {"add", "delete"},
    "deploy-key": {"add", "delete"},
    "gpg-key": {"add", "delete"},
    "incident": {"close", "note", "reopen", "subscribe", "unsubscribe"},
    "milestone": {"create", "delete", "edit"},
    "packages": {"delete", "upload"},
    "runner": {"assign", "delete", "unassign", "update"},
    "runner-controller": {"create", "delete", "update"},
    "securefile": {"create", "remove", "update"},
    "stack": {"create", "delete", "sync"},
    "token": {"create", "revoke", "rotate"},
    "work-items": {"create", "delete", "update"},
}
# Same grounding as the gh side (glab 1.122.0).
GLAB_READ = {
    "view",
    "list",
    "status",
    "search",
    "diff",
    "watch",
    "help",
    "get",
    "download",
    "trace",
    "approvers",
    "contributors",
    "issues",
    "lint",
    "export",
    "jobs",
}
GLAB_READ_NOUNS = {"search", "iteration", "user"}
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
    unrecognized_verb: bool = False
    workdir: Path | None = None
    text_by_substitution: bool = False
    text_file_missing: bool = False
    no_verify: bool = False
    hooks_path_override: bool = False
    reads_secret_file: list[str] = field(default_factory=list)
    writes_guard_config: list[str] = field(default_factory=list)
    prints_secret: str = ""
    printed_variables: list[str] = field(default_factory=list)
    script: str = ""
    starts_run: bool = False

    @property
    def program(self) -> str:
        """The program this simple command runs once wrappers and redirections are stripped,
        or an empty string when nothing is left."""
        rest = _strip_wrappers(_strip_redirections(self.tokens))
        return _basename(rest[0]) if rest else ""

    @property
    def sets_variables(self) -> set[str]:
        """The variables this simple command sets for what it runs."""
        return assigned_names(self.tokens)

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
        """True when at least one simple command was recognised as git, gh or glab. A file read
        is not a trace: "cat README.md; python3 -c ..." must not hide the interpreter call."""
        return any(c.kind not in ("other", "read") for c in self.commands)


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
    """Drop redirection operators, their file operands and a file-descriptor digit before them.
    Every redirection operator, the descriptor forms ``>&`` and ``<&`` included, consumes the
    next token as its target."""
    out: list[str] = []
    skip_next = False
    for token in tokens:
        if skip_next:
            skip_next = False
            continue
        if token in REDIRECT_TOKENS:
            if out and out[-1].isdigit() and len(out[-1]) == 1:
                out.pop()
            skip_next = True
            continue
        out.append(token)
    return out


# shlex builds each token a character at a time, which is quadratic in the token's length: one
# 1 MB word took 20 s, near the hook's timeout. Spans shlex gives no structure (a single-quoted
# string, a double-quoted one with no backslash, a run of plain word characters) are swapped
# for a placeholder before it runs and put back in the tokens after, so the tokens are unchanged.
LONG_SPAN = 4096
PLAIN_STOP = frozenset(" \t\r\n'\"\\();<>|&")
PLACEHOLDER_RE = re.compile("\ue000([0-9]+)\ue001")


def tokenize(line: str) -> list[str]:
    shielded, spans = _shield_long_spans(line)
    lexer = shlex.shlex(shielded, posix=True, punctuation_chars=True)
    lexer.whitespace_split = True
    lexer.commenters = ""
    try:
        tokens = list(lexer)
    except ValueError:
        return line.split()
    if not spans:
        return tokens
    return [PLACEHOLDER_RE.sub(lambda m: spans[int(m.group(1))], tok) for tok in tokens]


def _shield_long_spans(line: str) -> tuple[str, list[str]]:
    """``line`` with each literal span of LONG_SPAN characters or more replaced by a numbered
    placeholder, and the spans. A linear scan that follows shlex's quoting rules."""
    if len(line) < LONG_SPAN or "\ue000" in line or "\ue001" in line:
        return line, []
    spans: list[str] = []
    out: list[str] = []

    def keep(text: str, quote: str = "") -> None:
        if len(text) >= LONG_SPAN:
            out.append(f"{quote}\ue000{len(spans)}\ue001{quote}")
            spans.append(text)
        else:
            out.append(f"{quote}{text}{quote}")

    i, n = 0, len(line)
    while i < n:
        c = line[i]
        if c == "'":
            end = line.find("'", i + 1)
            if end < 0:
                break
            keep(line[i + 1 : end], "'")
            i = end + 1
        elif c == '"':
            end, escaped = i + 1, False
            while end < n and line[end] != '"':
                escaped = escaped or line[end] == "\\"
                end += 2 if line[end] == "\\" else 1
            if end >= n:
                break
            if escaped:
                out.append(line[i : end + 1])
            else:
                keep(line[i + 1 : end], '"')
            i = end + 1
        elif c == "\\":
            out.append(line[i : i + 2])
            i += 2
        elif c in PLAIN_STOP:
            out.append(c)
            i += 1
        else:
            end = i
            while end < n and line[end] not in PLAIN_STOP:
                end += 1
            keep(line[i:end])
            i = end
    out.append(line[i:])
    return "".join(out), spans


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


def _strip_wrappers(tokens: list[str], assigned: set[str] | None = None) -> list[str]:
    """Drop variable assignments and wrapper programs (with their options) from the front.
    The names of the dropped assignments are added to ``assigned`` when it is given."""
    rest = list(tokens)
    hops = 0
    while rest and hops < 8:
        head = rest[0]
        if ENV_ASSIGN_RE.match(head):
            if assigned is not None:
                assigned.add(head.split("=", 1)[0])
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


# Builtins that put a variable in the environment of the shell and of what it runs next.
EXPORTERS = {"export", "declare", "typeset", "readonly", "local"}
NAME_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


def assigned_names(tokens: list[str]) -> set[str]:
    """The variables a simple command sets for what it runs: leading NAME=value words, the
    NAME=value arguments of env and the other wrappers, and the names given to export,
    declare, typeset, readonly or local. A word that only names a variable is not one."""
    assigned: set[str] = set()
    rest = _strip_wrappers(_strip_redirections(tokens), assigned)
    if rest and _basename(rest[0]) in EXPORTERS:
        for word in rest[1:]:
            if word.startswith("-"):
                continue
            name = word.split("=", 1)[0]
            if NAME_RE.match(name):
                assigned.add(name)
    return assigned


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
    stripped = _strip_redirections(tokens)
    writes, reads = redirect_targets(tokens)
    rest = _strip_wrappers(stripped)
    facts.prints_secret, facts.printed_variables = environment_print(stripped)
    code = inline_code(rest)
    if not code:
        shell, script = script_file(rest, cwd)
        if shell:
            facts.script = script  # the guard parses it as shell
        elif script:
            code = [script]
    code_words = [word for text in code for word in PATHLIKE_RE.findall(text)]
    code_writes = [
        w for text in code if CODE_WRITE_RE.search(text) for w in PATHLIKE_RE.findall(text)
    ]
    targets = writes + file_write_targets(rest) + code_writes
    facts.writes_guard_config = _unique([t for t in targets if is_guard_config(t)])
    if not rest:
        facts.reads_secret_file = _unique([r for r in reads if is_secret_file(r)])
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
    elif program in SECRET_PRINTERS:
        operands = [a for a in args if not a.startswith("-")]
        facts.reads_secret_file = [a for a in operands if is_secret_file(a)]
    elif program == "agentic-sdlc" and args[:1] == ["run"] and "--dry-run" not in args:
        facts.starts_run = True
    elif program == "gh":
        _classify_gh(facts, args)
    elif program == "glab":
        _classify_glab(facts, args)
    hidden = [r for r in reads + code_words if is_secret_file(r)]
    facts.reads_secret_file = _unique(facts.reads_secret_file + hidden)
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


def _unique(items: list[str]) -> list[str]:
    return list(dict.fromkeys(items))


# Environment variables that set git configuration for every git call they reach, hooksPath
# included (GUARD-1).
GIT_CONFIG_ENV = {
    "GIT_CONFIG_PARAMETERS",
    "GIT_CONFIG_COUNT",
    "GIT_CONFIG_GLOBAL",
    "GIT_CONFIG_SYSTEM",
    "GIT_CONFIG",
}


def sets_git_config(name: str) -> bool:
    """True for a variable that hands git configuration to the git calls after it."""
    return name in GIT_CONFIG_ENV or name.startswith(("GIT_CONFIG_KEY_", "GIT_CONFIG_VALUE_"))


def is_guard_config(path: str) -> bool:
    """True when the path names a file whose change alters what the guard does (GUARD-2)."""
    return GUARD_CONFIG_RE.search(path.replace("\\", "/")) is not None


def redirect_targets(tokens: list[str]) -> tuple[list[str], list[str]]:
    """The files a simple command's redirections write and read. A descriptor (2>&1, >&-) is
    not a file; a heredoc tag and a here-string are not files either."""
    writes: list[str] = []
    reads: list[str] = []
    for index, token in enumerate(tokens[:-1]):
        target = tokens[index + 1]
        if token in OUTPUT_REDIRECTS and not target.isdigit() and target != "-":
            writes.append(target)
        elif token == "<":
            reads.append(target)
    return writes, reads


def file_write_targets(rest: list[str]) -> list[str]:
    """The files a program named on the command line changes: every operand of tee, rm, mv,
    chmod and the like, the last operand of cp, install, ln and rsync, the operands of sed or
    perl given -i, and dd's of= file."""
    if not rest:
        return []
    program = _basename(rest[0])
    args = rest[1:]
    operands = [a for a in args if not a.startswith("-")]
    if program in FILE_CHANGERS:
        return operands
    if program in FILE_COPIERS:
        return operands[-1:]
    if program in IN_PLACE_EDITORS:
        in_place = any(
            a.startswith("--in-place") or ("i" in _short_flags(a) and not a.startswith("--"))
            for a in args
        )
        return operands if in_place else []
    if program == "dd":
        return [a[3:] for a in args if a.startswith("of=")]
    return []


def flag_values(
    args: list[str], letters: str, longs: Iterable[str], attached: bool = False
) -> list[str]:
    """The values given to the short flags in letters (-c 'x'; -c'x' when attached is set) and
    to the long flags in longs (--eval 'x', --eval='x')."""
    out: list[str] = []
    for index, token in enumerate(args):
        if token.startswith("--"):
            key, eq, value = token.partition("=")
            if key in longs:
                if eq:
                    out.append(value)
                elif index + 1 < len(args):
                    out.append(args[index + 1])
            continue
        flags = _short_flags(token)
        if not flags:
            continue
        if flags[-1] in letters and index + 1 < len(args):
            out.append(args[index + 1])
        elif attached and flags[0] in letters and len(flags) > 1 and not flags[1:].isalpha():
            out.append(flags[1:])
    return out


def inline_code(rest: list[str]) -> list[str]:
    """The code an interpreter runs from its own command line (python -c, node -e, perl -e,
    ruby -e, php -r, bun -e, deno eval), which the parser can read but not follow."""
    if not rest:
        return []
    name = _basename(rest[0])
    args = rest[1:]
    if name == "deno":
        return args[1:2] if args[:1] == ["eval"] else []
    letters = "c" if PYTHON_RE.match(name) else INLINE_CODE_FLAGS.get(name)
    if letters is None:
        return []
    return flag_values(args, letters, INLINE_CODE_LONG, attached=True)


def script_file(rest: list[str], cwd: Path | None) -> tuple[bool, str]:
    """The script an interpreter runs from a file (bash deploy.sh, python3 tool.py, node x.js)
    as (is_shell, text). Only a script with uncommitted changes is opened: new, edited, ignored,
    untracked, or outside any repository. A committed script is reviewed code. A secret file is
    never opened, and neither is a file over 256 KB."""
    if not rest:
        return False, ""
    name = _basename(rest[0])
    args = rest[1:]
    shell = name in SHELLS
    if name == "deno":
        args = args[1:] if args[:1] == ["run"] else []
    elif not (shell or PYTHON_RE.match(name) or name in SCRIPT_RUNNERS):
        return False, ""
    operand = ""
    for token in args:
        flags = _short_flags(token)
        if (shell and "c" in flags) or (PYTHON_RE.match(name) and "m" in flags):
            return False, ""  # inline code or a module, not a file
        if not token.startswith("-"):
            operand = token
            break
    script = _resolve(cwd, operand) if operand else None
    if script is None or is_secret_file(operand):
        return False, ""
    try:
        if not script.is_file() or script.stat().st_size > SCRIPT_LIMIT or _committed(script):
            return False, ""
        return shell, script.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return False, ""


def _committed(file: Path) -> bool:
    """True when git tracks the file and it has no change in the work tree or the index."""
    try:
        result = subprocess.run(
            ["git", "-C", str(file.parent), "status", "--porcelain", "--ignored", "--", file.name],
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return False
    return result.returncode == 0 and not result.stdout.strip()


def environment_value(name: str) -> str:
    """A variable's value in the hook's environment, which the shell tool's commands inherit.
    The guard matches it against patterns and never puts it into a reason."""
    return os.environ.get(name, "")


def secret_variable(name: str) -> bool:
    """True when a variable's name marks it as holding a credential: GITLAB_TOKEN,
    AWS_SECRET_ACCESS_KEY, DB_PASSWORD. PATH, HOME and PWD are not."""
    upper = name.upper()
    parts = upper.split("_")
    return any(part in SECRET_NAME_PARTS for part in parts) or upper.endswith(SECRET_NAME_ENDINGS)


def environment_print(stripped: list[str]) -> tuple[str, list[str]]:
    """Why a simple command prints credentials from the environment (SECRET-2), and the
    variables it prints by name. The reason covers the whole environment (env or printenv with
    no command or name, export -p, declare -p, set alone) and a variable whose name marks a
    credential; the guard checks the values of the other printed variables."""
    rest = list(stripped)
    while rest and ENV_ASSIGN_RE.match(rest[0]):
        rest.pop(0)
    if not rest:
        return "", []
    reason, printed = _environment_print(rest)
    return reason, printed


def _environment_print(rest: list[str]) -> tuple[str, list[str]]:
    name = _basename(rest[0])
    args = rest[1:]
    if name == "env":
        if any(a in ("-i", "--ignore-environment") or a == "-" for a in args):
            return "", []
        index = 0
        while index < len(args):
            token = args[index]
            if token in ("-u", "--unset", "-C", "--chdir"):
                index += 2
                continue
            if token.startswith("-") or ENV_ASSIGN_RE.match(token):
                index += 1
                continue
            return "", []  # env runs a command: a wrapper, not a print
        return "env with no command prints the whole environment, credentials included", []
    if name == "printenv":
        names = [a for a in args if not a.startswith("-")]
        if not names:
            return "printenv with no name prints the whole environment, credentials included", []
        secret = [n for n in names if secret_variable(n)]
        if secret:
            return f"printenv {' '.join(secret[:3])} prints a credential", names
        return "", names
    if name in ("export", "declare", "typeset") and all(a.startswith("-") for a in args):
        if name == "export" or any(set(_short_flags(a)) & {"p", "x"} for a in args):
            return f"{' '.join(rest)} prints every exported variable, credentials included", []
        return "", []
    if name == "set" and not args:
        return "set with no arguments prints every variable, credentials included", []
    if name in ("echo", "printf"):
        named = _unique([m.group(1) for a in args for m in VAR_REF_RE.finditer(a)])
        secret = [n for n in named if secret_variable(n)]
        if secret:
            return f"{name} ${secret[0]} prints a credential", named
        return "", named
    return "", []


def database_write(tokens: list[str], clients: Iterable[str]) -> tuple[str, list[str]]:
    """Why a database client call can change data (PROD-1), with the statements it was given.
    It can change data when a statement writes, or when the hook cannot read the statements (a
    file, stdin, an interactive session, a client it has no flag table for). The reason is empty
    for a client call that only runs read statements, or for a program that is no client."""
    rest = _strip_wrappers(_strip_redirections(tokens))
    if not rest or _basename(rest[0]) not in set(clients):
        return "", []
    statements = _statements(rest)
    return _database_write(rest, statements), statements


def _statements(rest: list[str]) -> list[str]:
    name = _basename(rest[0])
    if name not in QUERY_FLAGS:
        return []
    letters, longs = QUERY_FLAGS[name]
    return flag_values(rest[1:], letters, longs)


def _database_write(rest: list[str], statements: list[str]) -> str:
    name = _basename(rest[0])
    args = rest[1:]
    if name == "pg_restore":
        return "pg_restore writes a dump into the database"
    if name == "redis-cli":
        index = 0
        while index < len(args):
            token = args[index]
            if token in REDIS_VALUE_FLAGS:
                index += 2
                continue
            if token.startswith("-"):
                index += 1
                continue
            verb = token.lower()
            if verb in REDIS_WRITE_VERBS:
                return f"runs the write command {token}"
            return ""
        return "reads its commands from stdin or an interactive session, which the hook cannot see"
    if name not in QUERY_FLAGS:
        return f"{name} has no statement flags the hook knows, so any call may write"
    file_flags = QUERY_FILE_FLAGS.get(name, ())
    for token in args:
        key, _, value = token.partition("=")
        if key in file_flags:
            return f"runs the statements in a file ({value or 'named after ' + key}), which the hook does not open"
    if not statements:
        return "reads its statements from stdin, a file or an interactive session, which the hook cannot see"
    text = " ".join(statements)
    found = SQL_WRITE_RE.search(text) or MONGO_WRITE_RE.search(text)
    if found:
        return f"runs a write ({found.group(0).strip()[:24]})"
    return ""


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
    elif (
        verb
        and not group.startswith("-")
        and not verb.startswith("-")
        and group not in GH_READ_NOUNS
        and verb not in GH_READ
    ):
        facts.unrecognized_verb = True
        facts.post_reason = f"gh {group} {verb}"


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
    elif (
        verb
        and not group.startswith("-")
        and not verb.startswith("-")
        and group not in GLAB_READ_NOUNS
        and verb not in GLAB_READ
    ):
        facts.unrecognized_verb = True
        facts.post_reason = f"glab {group} {verb}"


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
