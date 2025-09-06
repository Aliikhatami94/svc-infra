from dotenv import load_dotenv, find_dotenv

load_dotenv(find_dotenv(usecwd=True))

"""svc-infra: Infrastructure for building and deploying prod-ready services."""

__version__ = "0.1.124"

from . import app, api

__all__ = ["app", "api"]
