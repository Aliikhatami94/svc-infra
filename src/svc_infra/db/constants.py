import re

AL_EMBIC_DIR = "migrations"
ALEMBIC_INI = "alembic.ini"

_ENV_NAME_RE = re.compile(r'^\$?[A-Z_][A-Z0-9_]*$')
_ENV_NAME_BRACED_RE = re.compile(r'^\$\{[A-Za-z_][A-Za-z0-9_]*\}$')

_ENV_PLACEHOLDER_RE = re.compile(
    r'^\s*\$?\{?\s*([A-Za-z_][A-Za-z0-9_]*)\s*\}?\s*$'
)