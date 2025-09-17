from typing import Any, Dict


def providers_from_settings(settings: Any) -> Dict[str, Dict[str, Any]]:
    """
    Returns a registry of providers:
      {
        "<name>": {
          "kind": "oidc" | "oauth2" | "github" | "linkedin",
          # For "oidc":
          "issuer": "...",
          "client_id": "...",
          "client_secret": "...",
          "scope": "openid email profile",
          # For "oauth2"/custom:
          "authorize_url": "...",
          "access_token_url": "...",
          "api_base_url": "...",
          "scope": "..."
        }
      }
    """
    reg: Dict[str, Dict[str, Any]] = {}

    # Google (OIDC)
    if getattr(settings, "google_client_id", None) and getattr(
        settings, "google_client_secret", None
    ):
        reg["google"] = {
            "kind": "oidc",
            "issuer": "https://accounts.google.com",
            "client_id": settings.google_client_id,
            "client_secret": settings.google_client_secret.get_secret_value(),
            "scope": "openid email profile",
        }

    # GitHub (non-OIDC)
    if getattr(settings, "github_client_id", None) and getattr(
        settings, "github_client_secret", None
    ):
        reg["github"] = {
            "kind": "github",
            "authorize_url": "https://github.com/login/oauth/authorize",
            "access_token_url": "https://github.com/login/oauth/access_token",
            "api_base_url": "https://api.github.com/",
            "client_id": settings.github_client_id,
            "client_secret": settings.github_client_secret.get_secret_value(),
            "scope": "user:email",
        }

    # Microsoft Entra ID (Azure AD) – OIDC via tenant
    if (
        getattr(settings, "ms_client_id", None)
        and getattr(settings, "ms_client_secret", None)
        and getattr(settings, "ms_tenant", None)
    ):
        tenant = settings.ms_tenant
        reg["microsoft"] = {
            "kind": "oidc",
            "issuer": f"https://login.microsoftonline.com/{tenant}/v2.0",
            "client_id": settings.ms_client_id,
            "client_secret": settings.ms_client_secret.get_secret_value(),
            "scope": "openid email profile",
        }

    # LinkedIn (non-OIDC)
    if getattr(settings, "li_client_id", None) and getattr(settings, "li_client_secret", None):
        reg["linkedin"] = {
            "kind": "linkedin",
            "authorize_url": "https://www.linkedin.com/oauth/v2/authorization",
            "access_token_url": "https://www.linkedin.com/oauth/v2/accessToken",
            "api_base_url": "https://api.linkedin.com/v2/",
            "client_id": settings.li_client_id,
            "client_secret": settings.li_client_secret.get_secret_value(),
            "scope": "r_liteprofile r_emailaddress",
        }

    # Generic OIDC providers list (Okta, Auth0, Keycloak, Azure via issuer)
    for p in getattr(settings, "oidc_providers", []) or []:
        reg[p.name] = {
            "kind": "oidc",
            "issuer": p.issuer.rstrip("/"),
            "client_id": p.client_id,
            "client_secret": p.client_secret.get_secret_value(),
            "scope": p.scope or "openid email profile",
        }

    return reg
