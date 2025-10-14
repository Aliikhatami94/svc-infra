from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Callable, Iterable, Optional

COMMON_PASSWORDS = {"password", "123456", "qwerty", "letmein", "admin"}

HIBP_DISABLED = False  # default enabled; can be toggled via settings at startup


@dataclass
class PasswordPolicy:
    min_length: int = 12
    require_upper: bool = True
    require_lower: bool = True
    require_digit: bool = True
    require_symbol: bool = True
    forbid_common: bool = True
    forbid_breached: bool = True  # will toggle off if HIBP integration not configured
    symbols_regex: str = r"[!@#$%^&*()_+=\-{}\[\]:;,.?/]"


class PasswordValidationError(Exception):
    def __init__(self, reasons: Iterable[str]):
        super().__init__("Password validation failed")
        self.reasons = list(reasons)


UPPER = re.compile(r"[A-Z]")
LOWER = re.compile(r"[a-z]")
DIGIT = re.compile(r"[0-9]")
SYMBOL = re.compile(r"[!@#$%^&*()_+=\-{}\[\]:;,.?/]")


BreachedChecker = Callable[[str], bool]


_breached_checker: Optional[BreachedChecker] = None


def configure_breached_checker(checker: Optional[BreachedChecker]) -> None:
    global _breached_checker
    _breached_checker = checker


def validate_password(pw: str, policy: PasswordPolicy | None = None) -> None:
    policy = policy or PasswordPolicy()
    reasons: list[str] = []
    if len(pw) < policy.min_length:
        reasons.append(f"min_length({policy.min_length})")
    if policy.require_upper and not UPPER.search(pw):
        reasons.append("missing_upper")
    if policy.require_lower and not LOWER.search(pw):
        reasons.append("missing_lower")
    if policy.require_digit and not DIGIT.search(pw):
        reasons.append("missing_digit")
    if policy.require_symbol and not SYMBOL.search(pw):
        reasons.append("missing_symbol")
    if policy.forbid_common:
        lowered = pw.lower()
        # Reject if whole password matches a common one or contains it as a substring
        if lowered in COMMON_PASSWORDS or any(term in lowered for term in COMMON_PASSWORDS):
            reasons.append("common_password")
    if policy.forbid_breached and not HIBP_DISABLED:
        if _breached_checker and _breached_checker(pw):
            reasons.append("breached_password")
    if reasons:
        raise PasswordValidationError(reasons)


__all__ = [
    "PasswordPolicy",
    "validate_password",
    "PasswordValidationError",
    "configure_breached_checker",
]
