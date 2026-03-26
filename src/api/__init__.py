"""API module for SA Voices"""

from .server import create_app
from .endpoints import router

__all__ = ["create_app", "router"]
