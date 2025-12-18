from __future__ import annotations

from collections.abc import Iterable
from typing import Any

import jwt
from fastapi_users.authentication.strategy.jwt import JWTStrategy
from fastapi_users.jwt import decode_jwt


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
        old_secrets: Iterable[str] | None = None,
        token_audience: str | list[str] | None = None,
    ):
        # Normalize token_audience to list as required by parent JWTStrategy
        aud_list: list[str] = (
            [token_audience]
            if isinstance(token_audience, str)
            else list(token_audience)
            if token_audience
            else []
        ) or ["fastapi-users:auth"]
        super().__init__(secret=secret, lifetime_seconds=lifetime_seconds, token_audience=aud_list)
        self._verify_secrets: list[str] = [secret, *list(old_secrets or [])]
        self._lifetime_seconds = lifetime_seconds

    async def read_token(
        self,
        token: str | None,
        user_manager: Any = None,
        *,
        audience: str | list[str] | None = None,
    ) -> Any:
        """Read/verify a token against the active + rotated secrets.

        Compatibility:
        - fastapi-users signature: (token, user_manager) -> user | None
        - legacy/test helper usage: (token, *, audience=...) -> claims | None
        """

        if token is None:
            return None

        if user_manager is None:
            aud_list: list[str]
            if audience is None:
                aud_list = self.token_audience
            elif isinstance(audience, str):
                aud_list = [audience]
            else:
                aud_list = audience
            try:
                return decode_jwt(token, self.decode_key, aud_list, algorithms=[self.algorithm])
            except jwt.PyJWTError:
                pass

            for secret in self._verify_secrets[1:]:
                candidate: JWTStrategy[Any, Any] = JWTStrategy(
                    secret=secret,
                    lifetime_seconds=self._lifetime_seconds,
                    token_audience=self.token_audience,
                )
                try:
                    return decode_jwt(
                        token,
                        candidate.decode_key,
                        aud_list,
                        algorithms=[candidate.algorithm],
                    )
                except jwt.PyJWTError:
                    continue
            raise ValueError("Invalid token for all configured secrets")

        user = await super().read_token(token, user_manager)
        if user is not None:
            return user

        for secret in self._verify_secrets[1:]:
            candidate = JWTStrategy(
                secret=secret,
                lifetime_seconds=self._lifetime_seconds,
                token_audience=self.token_audience,
            )
            user = await candidate.read_token(token, user_manager)
            if user is not None:
                return user

        return None


__all__ = ["RotatingJWTStrategy"]
