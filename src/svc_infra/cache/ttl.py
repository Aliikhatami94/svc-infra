import os

TTL_DEFAULT = int(os.getenv("CACHE_TTL_DEFAULT", "300"))
TTL_SHORT = int(os.getenv("CACHE_TTL_SHORT", "30"))
TTL_LONG = int(os.getenv("CACHE_TTL_LONG", "3600"))
