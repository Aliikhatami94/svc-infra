from datetime import datetime, timezone

from svc_infra.api.fastapi.auth.settings import get_auth_settings


def get_mfa_pre_jwt_writer():
    st = get_auth_settings()
    jwt_block = getattr(st, "jwt", None)

    # Force to plain string
    secret = (
        jwt_block.secret.get_secret_value()
        if jwt_block and getattr(jwt_block, "secret", None)
        else "svc-dev-secret-change-me"
    )
    secret = str(secret)

    lifetime = int(getattr(st, "mfa_pre_token_lifetime_seconds", 300))

    class PreTokenWriter:
        def __init__(self, secret: str, lifetime: int):
            self.secret = secret
            self.lifetime = lifetime

        async def write(self, user):
            from fastapi_users.jwt import generate_jwt

            now = datetime.now(timezone.utc)
            payload = {
                "sub": str(getattr(user, "id")),
                "aud": ["fastapi-users:mfa"],
                "iat": int(now.timestamp()),
                "exp": int(now.timestamp()) + self.lifetime,
            }
            return generate_jwt(payload, self.secret, algorithm="HS256")

        async def read(self, token: str):
            from fastapi_users.jwt import decode_jwt

            # IMPORTANT: pass a STRING, not a list
            return decode_jwt(token, self.secret, audience=["fastapi-users:mfa"])

    return PreTokenWriter(secret, lifetime)
