"""Pattern checks over text: tool attribution, key-shaped literals, and the mechanical part
of the plain-voice rules.

Every function returns ``Finding`` objects and never raises on odd input. Secret findings
carry the pattern name and the line number, never the matched value.
"""

from __future__ import annotations

import re
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
        trailer = TRAILER_RE.match(line)
        if trailer:
            value = trailer.group("value")
            if vendor_word.search(value) or domain_re.search(value):
                findings.append(Finding("ATTR-1", "tool trailer", number, stripped[:120]))
                continue
        if footer_re.search(line):
            findings.append(Finding("ATTR-1", "generated-with footer", number, stripped[:120]))
            continue
        if ROBOT_RE.search(line):
            findings.append(Finding("ATTR-1", "robot emoji", number, stripped[:120]))
            continue
        if strict_re is not None and strict_re.search(line):
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
        r"(?i)\b(?:100%|zero data loss|on track|confirmed|resolved)\b(?!.*\b(?:Verified|Measured|Inferred|Planned)\b)",
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
