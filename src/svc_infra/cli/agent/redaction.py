import re

_SECRET_RE = re.compile(
    r'(?P<scheme>\b[a-zA-Z][a-zA-Z0-9+\-.]*://)'
    r'(?:(?P<user>[^:/\s@]+)(?::(?P<pw>[^@\s]+))?@)?'
)
# Additional redaction patterns
_SQL_PASSWORD_QUOTED_RE = re.compile(r"(?i)(password\s*)(['\"])[^'\"]*(\2)")
_EQ_PASSWORD_QUOTED_RE = re.compile(r"(?i)(password\s*=\s*)(['\"])[^'\"]*(\2)")
_CLI_PASSWORD_EQ_RE = re.compile(r"(?i)(--password\s*=\s*)([^\s]+)")
_CLI_PASSWORD_SPACE_RE = re.compile(r"(?i)(--password)(\s+)([^\s]+)")
_ENV_PGPASSWORD_RE = re.compile(r"(?i)(pgpassword\s*=\s*)([^\s]+)")

def _redact_secrets(text: str) -> str:
    def _sub(m):
        scheme = m.group("scheme") or ""
        user = m.group("user")
        return f"{scheme}***:***@" if user else scheme
    return _SECRET_RE.sub(_sub, text or "")

def _redact(text: str) -> str:
    """Redact secrets in URLs and common CLI/SQL password patterns."""
    t = _redact_secrets(text or "")
    t = _SQL_PASSWORD_QUOTED_RE.sub(r"\1'***'", t)
    t = _EQ_PASSWORD_QUOTED_RE.sub(r"\1'***'", t)
    t = _CLI_PASSWORD_EQ_RE.sub(r"\1***", t)
    # Normalize space form to equals form while redacting
    t = _CLI_PASSWORD_SPACE_RE.sub(r"\1=***", t)
    t = _ENV_PGPASSWORD_RE.sub(r"\1***", t)
    return t