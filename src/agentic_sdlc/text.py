"""Pattern checks over text: tool attribution, key-shaped literals, the mechanical part of
the plain-voice rules, and the structure of skill files (code fences, contents lists,
metadata values).

No function raises on odd input. The rule checks return ``Finding`` objects; secret findings
carry the pattern name and the line number, never the matched value.
"""

from __future__ import annotations

import re
import unicodedata
from collections.abc import Iterable
from dataclasses import dataclass

from . import config as config_mod


@dataclass(frozen=True)
class Finding:
    rule: str
    name: str
    line: int
    excerpt: str

    def describe(self) -> str:
        where = f"line {self.line}" if self.line else "text"
        return f"{self.rule} {self.name} at {where}: {self.excerpt}".rstrip(": ")


def _vendor_alternation(vendors: Iterable[str]) -> str:
    parts = sorted(
        {re.escape(v.strip().lower()) for v in vendors if v.strip()}, key=len, reverse=True
    )
    return "|".join(p.replace(r"\ ", r"[\s-]*") for p in parts)


TRAILER_RE = re.compile(
    r"^\s*(co-authored-by|signed-off-by|reviewed-by|assisted-by|generated-by|authored-by|"
    r"co-developed-by|suggested-by|helped-by|commit-generated-by)\s*:\s*(?P<value>.+)$",
    re.IGNORECASE,
)
FOOTER_VERBS = (
    r"(generated|written|authored|created|drafted|made|produced|composed|co-authored|assisted)"
)
ROBOT_RE = re.compile("\U0001f916")

# A footer verb followed by a capitalized token that reads as a product name (an inner
# uppercase letter or a digit, as in DevTool9000) is attribution even when the vendor list
# does not know the name: a human never writes "Generated with X". A plain lowercase word
# ("generated with care") or an ordinary capitalized word ("written with Rust") stays clean.
FOOTER_TOOL_RE = re.compile(
    rf"(?i:\b{FOOTER_VERBS}\s+(?:with|by|using)\s+(?:the\s+|an?\s+)?)(?P<token>[A-Z][A-Za-z0-9_-]*)"
)


def _tool_shaped(token: str) -> bool:
    body = token[1:]
    return any(c.isupper() for c in body) or any(c.isdigit() for c in body)


# Cyrillic and Greek letters that look like ASCII ones, mapped so a homoglyph cannot hide a
# vendor name or a trailer key from the patterns.
_CONFUSABLES = {
    "а": "a",
    "е": "e",
    "о": "o",
    "р": "p",
    "с": "c",
    "х": "x",
    "у": "y",
    "А": "A",
    "Е": "E",
    "О": "O",
    "Р": "P",
    "С": "C",
    "Х": "X",
    "У": "Y",
    "α": "a",
    "ε": "e",
    "ο": "o",
    "ρ": "p",
    "χ": "x",
}


def _normalize(line: str) -> str:
    """The line as the patterns should see it: NFKD, format characters (zero-width joiners
    and spaces, the soft hyphen) removed, confusable letters as ASCII."""
    out = []
    for ch in unicodedata.normalize("NFKD", line):
        if unicodedata.category(ch) == "Cf":
            continue
        out.append(_CONFUSABLES.get(ch, ch))
    return "".join(out)


def attribution_findings(text: str, cfg: config_mod.Config | None = None) -> list[Finding]:
    """ATTR-1 always; ATTR-2 when the config is strict."""
    cfg = cfg or config_mod.Config()
    findings: list[Finding] = []
    trailer_vendors = _vendor_alternation(cfg.trailer_vendors)
    vendor_word = re.compile(rf"\b(?:{trailer_vendors})\b", re.IGNORECASE)
    domain_re = re.compile(
        r"@(?:" + "|".join(re.escape(d) for d in config_mod.VENDOR_EMAIL_DOMAINS) + r")\b",
        re.IGNORECASE,
    )
    footer_re = re.compile(
        rf"\b{FOOTER_VERBS}\s+(?:with|by|using)\s+(?:the\s+|an?\s+)?(?:\[)?(?:ai\b|llm\b|an?\s+ai\b|{trailer_vendors})",
        re.IGNORECASE,
    )
    strict_re = None
    if cfg.strict:
        strict_re = re.compile(rf"\b(?:{_vendor_alternation(cfg.strict_vendors)})\b", re.IGNORECASE)

    for number, line in enumerate(text.splitlines(), start=1):
        stripped = line.strip()
        if not stripped:
            continue
        scanned = _normalize(line)
        trailer = TRAILER_RE.match(scanned)
        if trailer:
            value = trailer.group("value")
            if vendor_word.search(value) or domain_re.search(value):
                findings.append(Finding("ATTR-1", "tool trailer", number, stripped[:120]))
                continue
        if footer_re.search(scanned):
            findings.append(Finding("ATTR-1", "generated-with footer", number, stripped[:120]))
            continue
        tool = FOOTER_TOOL_RE.search(scanned)
        if tool and _tool_shaped(tool.group("token")):
            findings.append(Finding("ATTR-1", "tool-named footer", number, stripped[:120]))
            continue
        if ROBOT_RE.search(scanned) and (
            vendor_word.search(scanned) or re.search(FOOTER_VERBS, scanned, re.I)
        ):
            findings.append(Finding("ATTR-1", "robot emoji", number, stripped[:120]))
            continue
        if strict_re is not None and strict_re.search(scanned):
            findings.append(Finding("ATTR-2", "vendor mention", number, stripped[:120]))
    return findings


SECRET_PATTERNS: list[tuple[str, str]] = [
    ("AWS access key id", r"\b(?:AKIA|ASIA)[0-9A-Z]{16}\b"),
    ("GitHub token", r"\bgh[pousr]_[A-Za-z0-9]{36,}\b"),
    ("GitHub fine-grained token", r"\bgithub_pat_[A-Za-z0-9_]{22,}\b"),
    ("GitLab token", r"\bglpat-[A-Za-z0-9_-]{20,}\b"),
    ("Slack token", r"\bxox[baprs]-[A-Za-z0-9-]{10,}\b"),
    ("Google API key", r"\bAIza[0-9A-Za-z_-]{35}\b"),
    ("Stripe key", r"\b[sr]k_(?:live|test)_[A-Za-z0-9]{16,}\b"),
    ("OpenAI-style key", r"\bsk-(?:ant-|proj-)?[A-Za-z0-9_-]{20,}\b"),
    ("npm token", r"\bnpm_[A-Za-z0-9]{36}\b"),
    ("PyPI token", r"\bpypi-AgEI[A-Za-z0-9_-]{20,}"),
    ("Hugging Face token", r"\bhf_[A-Za-z0-9]{30,}\b"),
    (
        "private key block",
        r"-----BEGIN (?:RSA |EC |DSA |OPENSSH |PGP |ENCRYPTED )?PRIVATE KEY(?: BLOCK)?-----",
    ),
    ("JSON web token", r"\beyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\b"),
    (
        "secret assignment",
        r"(?i)\b(?:api[_-]?key|secret[_-]?key|access[_-]?token|auth[_-]?token|client[_-]?secret|"
        r"private[_-]?key|signing[_-]?key|password|passwd)\b\s*[:=]\s*['\"]?(?P<value>[A-Za-z0-9/+_\-.=]{20,})['\"]?",
    ),
]
PLACEHOLDER_RE = re.compile(
    r"(?i)(example|placeholder|your[_-]|xxx|replace|dummy|sample|changeme|redacted|<[^>]+>|\$\{|\$\(|os\.environ|getenv|secrets\.)"
)


def secret_findings(text: str, extra_patterns: Iterable[str] = ()) -> list[Finding]:
    """SECRET-1 over arbitrary text. For a diff, pass only the added lines."""
    compiled: list[tuple[str, re.Pattern[str]]] = []
    for name, pattern in SECRET_PATTERNS:
        compiled.append((name, re.compile(pattern)))
    for index, pattern in enumerate(extra_patterns, start=1):
        try:
            compiled.append((f"custom pattern {index}", re.compile(pattern)))
        except re.error:
            continue
    findings: list[Finding] = []
    for number, line in enumerate(text.splitlines(), start=1):
        for name, pattern in compiled:
            match = pattern.search(line)
            if not match:
                continue
            value = match.groupdict().get("value") if match.groupdict() else None
            if name == "secret assignment" and value is not None and PLACEHOLDER_RE.search(line):
                continue
            findings.append(Finding("SECRET-1", name, number, "value withheld"))
            break
    return findings


FENCE_LINE_RE = re.compile(r"^\s*(`{3,}|~{3,})(.*)$")


def nested_fence_findings(body: str) -> list[tuple[int, int]]:
    """Fences with an info string that open inside a block of the same fence character and
    no greater length, as ``(line, opened_at)`` pairs with 1-based line numbers.

    CommonMark reads such a fence as content, so the next bare fence closes the outer block
    and the rest of the example renders as prose. The fix is a longer outer fence. After a
    finding the scan follows the author's intent (the inner block closes first, then the
    outer one), so one defect gives one finding. A bare inner fence looks like a closing
    fence and is not found."""
    findings: list[tuple[int, int]] = []
    stack: list[tuple[str, int]] = []
    for number, line in enumerate(body.splitlines(), 1):
        match = FENCE_LINE_RE.match(line)
        if not match:
            continue
        fence, info = match.group(1), match.group(2).strip()
        if fence[0] == "`" and "`" in info:
            continue  # not a fence line: a backtick fence's info string has no backticks
        if not stack:
            stack.append((fence, number))
            continue
        top, opened_at = stack[-1]
        if fence[0] != top[0] or len(fence) < len(top):
            continue  # content of the open block
        if info:
            findings.append((number, opened_at))
            stack.append((fence, number))
        else:
            stack.pop()
    return findings


# A plain YAML scalar that parses as a number, boolean, null or date, not a string.
YAML_NON_STRING_RE = re.compile(
    r"^(?:[-+]?(?:0|[1-9][0-9]*|0o[0-7]+|0x[0-9a-fA-F]+)"
    r"|[-+]?(?:\.[0-9]+|[0-9]+(?:\.[0-9]*)?)(?:[eE][-+]?[0-9]+)?"
    r"|[-+]?\.(?:inf|Inf|INF)|\.(?:nan|NaN|NAN)"
    r"|true|True|TRUE|false|False|FALSE|yes|Yes|YES|no|No|NO|on|On|ON|off|Off|OFF"
    r"|null|Null|NULL|~"
    r"|[0-9]{4}-[0-9]{2}-[0-9]{2}(?:[Tt ].*)?)$"
)


def metadata_problems(frontmatter: str) -> list[str]:
    """``metadata`` maps strings to strings. Reads the frontmatter text (between the ``---``
    lines) and the indented lines under a block-style
    ``metadata:`` key and names each value a YAML parser would not read as a string: a plain
    number, boolean, null or date, or a nested list or map. Quoted values and block scalars
    are strings."""
    lines = frontmatter.splitlines()
    start = next(
        (i for i, line in enumerate(lines) if re.match(r"^metadata:\s*(#.*)?$", line)), None
    )
    if start is None:
        return []
    block: list[str] = []
    for line in lines[start + 1 :]:
        if line.strip() and line[0] not in " \t":
            break
        block.append(line)
    content = [line for line in block if line.strip() and not line.strip().startswith("#")]
    if not content:
        return []
    indent = len(content[0]) - len(content[0].lstrip())
    entries: list[tuple[str, str, bool]] = []  # key, value, has deeper lines
    for line in content:
        depth = len(line) - len(line.lstrip())
        if depth > indent:
            if entries:
                key, value, _ = entries[-1]
                entries[-1] = (key, value, True)
            continue
        key, sep, value = line.strip().partition(":")
        if sep:
            entries.append((key.strip().strip("\"'"), value.strip(), False))
    problems = []
    for key, value, deeper in entries:
        if value[:1] not in ('"', "'"):
            value = re.sub(r"\s+#.*$", "", value)
        if value in ("|", ">", "|-", ">-", "|+", ">+"):
            continue
        if value[:1] in ("[", "{") or (value == "" and deeper):
            problems.append(
                f"metadata.{key} holds a nested value; metadata maps strings to strings"
            )
        elif value == "" or (value[:1] not in ('"', "'") and YAML_NON_STRING_RE.match(value)):
            problems.append(f"metadata.{key} is not a string; quote it")
    return problems


CONTENTS_RE = re.compile(r"^#{1,3} (?:Table of )?[Cc]ontents\s*$")


def has_contents_list(body: str) -> bool:
    """A Contents heading outside code blocks, with fences closed as CommonMark closes them."""
    fence: str | None = None
    for line in body.splitlines():
        match = FENCE_LINE_RE.match(line)
        if match:
            mark, info = match.group(1), match.group(2).strip()
            if fence is None:
                fence = mark
            elif mark[0] == fence[0] and len(mark) >= len(fence) and not info:
                fence = None
            continue
        if fence is None and CONTENTS_RE.match(line):
            return True
    return False


def added_lines(diff: str) -> str:
    """The added lines of a unified diff, without the leading plus, one per line."""
    out = []
    for line in diff.splitlines():
        if line.startswith("+") and not line.startswith("+++"):
            out.append(line[1:])
    return "\n".join(out)


# Mechanical subset of the plain-voice rules. Each entry: (rule id, name, level, pattern).
VOICE_PATTERNS: list[tuple[str, str, str, str]] = [
    ("VOICE-3", "em dash", "fail", "—"),
    ("VOICE-3", "spaced en dash used as a dash", "fail", r"\s–\s"),
    (
        "VOICE-4",
        "counting framing",
        "fail",
        r"(?i)\b(?:two|three|four|five|a couple of|a few|several)\s+(?:things|points|notes|items|reasons|takeaways|caveats|observations|quick things)\b",
    ),
    ("VOICE-4", "that is why", "fail", r"(?i)\bthat(?:'s| is)\s+why\b"),
    (
        "VOICE-5",
        "closing offer",
        "fail",
        r"(?i)\b(?:let me know if|i hope this helps|happy to (?:help|walk|dig)|feel free to|don'?t hesitate to)\b",
    ),
    (
        "VOICE-5",
        "chatbot opener",
        "fail",
        r"(?i)^\s*(?:great question|certainly!|of course!|absolutely!|sure thing)",
    ),
    (
        "VOICE-6",
        "banned word",
        "fail",
        r"(?i)\b(?:seamless(?:ly)?|robust(?:ly|ness)?|best-in-class|leverag(?:e|es|ed|ing)|comprehensive(?:ly)?|world-class|delve(?:s|d)?|tapestry|testament|cutting-edge|game-chang(?:er|ing))\b",
    ),
    (
        "VOICE-7",
        "throat clearing",
        "warn",
        r"(?i)^\s*(?:it(?:'s| is) worth noting|note that|importantly|interestingly|as you can see|in summary|in conclusion|to summari[sz]e|needless to say)\b",
    ),
    (
        "VOICE-8",
        "evidence word without a tag",
        "warn",
        r"(?i)(?<!\")(?<!is )(?<!are )(?<!was )(?<!were )(?<!been )(?<!be )(?<!the )\b(?:100%|zero data loss|on track|confirmed|resolved)\b(?!\")(?!.*\b(?:Verified|Measured|Inferred|Planned)\b)",
    ),
]


# A line that quotes the rules themselves is exempt: an explicit marker, or a table row
# that starts with a rule id, as docs/coverage.md renders.
VOICE_SKIP_RE = re.compile(r"voice-lint:\s*skip|^\s*\|\s*[A-Z]+-[0-9]+\s*\|")


def voice_findings(text: str, skip_code: bool = True) -> list[Finding]:
    """Findings for the mechanical plain-voice rules. Fenced code blocks are skipped."""
    compiled = [
        (rule, name, level, re.compile(pattern)) for rule, name, level, pattern in VOICE_PATTERNS
    ]
    findings: list[Finding] = []
    in_code = False
    for number, line in enumerate(text.splitlines(), start=1):
        if skip_code and line.lstrip().startswith("```"):
            in_code = not in_code
            continue
        if in_code or VOICE_SKIP_RE.search(line):
            continue
        for rule, name, level, pattern in compiled:
            if pattern.search(line):
                findings.append(Finding(rule, f"{name} [{level}]", number, line.strip()[:120]))
    return findings


def voice_level(finding: Finding) -> str:
    return "fail" if finding.name.endswith("[fail]") else "warn"
