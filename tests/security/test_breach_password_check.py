from __future__ import annotations

import pytest

from svc_infra.security.passwords import (
    PasswordPolicy,
    PasswordValidationError,
    configure_breached_checker,
    validate_password,
)


@pytest.fixture(autouse=True)
def reset_checker():
    # Ensure no global checker leaks between tests
    configure_breached_checker(None)
    yield
    configure_breached_checker(None)


def test_password_rejected_when_breached_checker_flags():
    policy = PasswordPolicy(min_length=6, require_symbol=False)

    def fake_checker(pw: str) -> bool:
        return pw == "Tr0ub4dor&3"

    configure_breached_checker(fake_checker)

    with pytest.raises(PasswordValidationError) as exc:
        validate_password("Tr0ub4dor&3", policy)
    assert "breached_password" in exc.value.reasons


def test_password_allowed_when_not_breached():
    policy = PasswordPolicy(min_length=6, require_symbol=False)

    def fake_checker(pw: str) -> bool:
        return False

    configure_breached_checker(fake_checker)

    # Should not raise
    validate_password("CorrectHorseBatteryStaple1", policy)
