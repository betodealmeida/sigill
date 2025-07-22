"""
Sigill prevents unauthorized SQL. Sigill only understand SQL.
"""

from .api import check, check_permission, tighten

__all__ = ["check", "check_permission", "tighten"]
