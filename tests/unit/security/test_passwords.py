from __future__ import annotations

import pytest

from svc_infra.security.passwords import PasswordPolicy, PasswordValidationError, validate_password


@pytest.mark.parametrize(
    "pw",
    [
        "Short7!",
        "alllowercase!!!",
        "NOUPPER123!!!",
        "NoDigits!!!!",
        "NoSymbols123",
        "passwordPASSWORD123!",
    ],
)
def test_password_invalid_cases(pw: str):
    policy = PasswordPolicy(min_length=12)
    with pytest.raises(PasswordValidationError) as exc:
        validate_password(pw, policy)
    # At least one reason returned
    assert len(exc.value.reasons) >= 1


def test_password_valid():
    pw = "ValidPass123!"  # length 13
    policy = PasswordPolicy(min_length=12)
    validate_password(pw, policy)  # should not raise


def test_common_password_rejected():
    with pytest.raises(PasswordValidationError) as exc:
        validate_password("passwordPASSWORD123!")
    assert "common_password" in exc.value.reasons
