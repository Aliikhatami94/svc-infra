from fastapi.security import APIKeyCookie, OAuth2PasswordBearer

from svc_infra.api.fastapi.auth.settings import get_auth_settings

# Note: auto_error=False so these don't 403 if missing; we only want them to appear in OpenAPI.
oauth2_scheme_optional = OAuth2PasswordBearer(tokenUrl="/auth/login", auto_error=False)
cookie_auth_optional = APIKeyCookie(name=get_auth_settings().auth_cookie_name, auto_error=False)
