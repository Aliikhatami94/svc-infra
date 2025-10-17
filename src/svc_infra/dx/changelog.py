from __future__ import annotations

from dataclasses import dataclass
from datetime import date as _date
from typing import Sequence


@dataclass(frozen=True)
class Commit:
    sha: str
    subject: str


_SECTION_ORDER = [
    ("feat", "Features"),
    ("fix", "Bug Fixes"),
    ("perf", "Performance"),
    ("refactor", "Refactors"),
]


def _classify(subject: str) -> tuple[str, str]:
    """Return (type, title) where title is display name of the section."""
    lower = subject.strip().lower()
    for t, title in _SECTION_ORDER:
        if lower.startswith(t + ":") or lower.startswith(t + "("):
            return (t, title)
    return ("other", "Other")


def _format_item(commit: Commit) -> str:
    subj = commit.subject.strip()
    # Strip leading type(scope): if present
    i = subj.find(": ")
    if i != -1 and i < 20:  # conventional commit prefix
        pretty = subj[i + 2 :].strip()
    else:
        pretty = subj
    return f"- {pretty} ({commit.sha})"


def generate_release_section(
    *,
    version: str,
    commits: Sequence[Commit],
    release_date: str | None = None,
) -> str:
    """Generate a markdown release section from commits.

    Group by type: feat, fix, perf, refactor; everything else under Other.
    """
    if release_date is None:
        release_date = _date.today().isoformat()

    buckets: dict[str, list[str]] = {k: [] for k, _ in _SECTION_ORDER}
    buckets["other"] = []

    for c in commits:
        typ, _ = _classify(c.subject)
        buckets.setdefault(typ, []).append(_format_item(c))

    lines: list[str] = [f"## v{version} - {release_date}", ""]
    for key, title in _SECTION_ORDER + [("other", "Other")]:
        items = buckets.get(key) or []
        if not items:
            continue
        lines.append(f"### {title}")
        lines.extend(items)
        lines.append("")

    return "\n".join(lines).rstrip() + "\n"


__all__ = ["Commit", "generate_release_section"]
