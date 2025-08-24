from typing import Any, Dict

def providers_from_settings(settings: Any) -> Dict[str, Dict[str, str]]:
    providers: Dict[str, Dict[str, str]] = {}
    if getattr(settings, "google_client_id", None) and getattr(settings, "google_client_secret", None):
        providers["google"] = {
            "client_id": settings.google_client_id,
            "client_secret": settings.google_client_secret.get_secret_value(),
        }
    if getattr(settings, "github_client_id", None) and getattr(settings, "github_client_secret", None):
        providers["github"] = {
            "client_id": settings.github_client_id,
            "client_secret": settings.github_client_secret.get_secret_value(),
        }
    return providers