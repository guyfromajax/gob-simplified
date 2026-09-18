"""Persistence adapter: collection handles plus franchise-scoped I/O.

Callers should use ``get_store()`` rather than importing ``BackEnd.db``.
``db.py`` remains a compatibility facade for tests and scripts.
"""

from BackEnd.persistence.guards import (
    ProdAccessBlocked,
    ProdWriteBlocked,
    _CLIENT_MUTATORS,
    _DATABASE_MUTATORS,
    _MUTATORS,
    _ReadOnlyClient,
    _ReadOnlyCollection,
    _ReadOnlyDatabase,
)
from BackEnd.persistence.protocol import FranchiseBundle, PersistenceStore
from BackEnd.persistence.store import create_store, get_store

__all__ = [
    "FranchiseBundle",
    "PersistenceStore",
    "ProdAccessBlocked",
    "ProdWriteBlocked",
    "create_store",
    "get_store",
    "_CLIENT_MUTATORS",
    "_DATABASE_MUTATORS",
    "_MUTATORS",
    "_ReadOnlyClient",
    "_ReadOnlyCollection",
    "_ReadOnlyDatabase",
]
