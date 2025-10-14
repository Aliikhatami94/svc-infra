from __future__ import annotations

from typing import Iterable, List, Optional, Union

import jwt as pyjwt
from fastapi_users.authentication.strategy.jwt import JWTStrategy


class RotatingJWTStrategy(JWTStrategy):
    """JWTStrategy that can verify tokens against multiple secrets.

    Signing uses the primary secret (as in base class). Verification accepts any of
    the provided secrets: [primary] + old_secrets.
    """

    def __init__(
        self,
        *,
        secret: str,
        lifetime_seconds: int,
        old_secrets: Optional[Iterable[str]] = None,
        token_audience: Optional[Union[str, List[str]]] = None,
    ):
        super().__init__(
            secret=secret, lifetime_seconds=lifetime_seconds, token_audience=token_audience
        )
        self._verify_secrets: List[str] = [secret] + list(old_secrets or [])

    async def read_token(self, token: str, audience: Optional[str] = None):  # type: ignore[override]
        # Try with current strategy's configured secret first
        eff_aud = audience or self.token_audience
        try:
            return await super().read_token(token, audience=eff_aud)
        except Exception:
            pass
        # Try older secrets
        for s in self._verify_secrets[1:]:
            try:
                data = pyjwt.decode(
                    token,
                    s,
                    algorithms=["HS256"],
                    audience=eff_aud,
                )
                if data is not None:
                    return data
            except Exception:
                pass
        # If none of the secrets validated the token, raise a generic error
        raise ValueError("Invalid token for all configured secrets")


__all__ = ["RotatingJWTStrategy"]
