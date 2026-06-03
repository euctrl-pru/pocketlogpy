"""pocketlogpy — Log application events to PocketBase from Python."""

from .admin import PocketLogAdmin
from .client import PocketLog
from .constants import FLOW_TYPES, LOG_TYPES, VALID_STATUSES
from .models import DagEntry, Dependency, Flow, LogEntry, StatusEntry

__all__ = [
    "PocketLog",
    "PocketLogAdmin",
    "FLOW_TYPES",
    "LOG_TYPES",
    "VALID_STATUSES",
    "Flow",
    "LogEntry",
    "Dependency",
    "StatusEntry",
    "DagEntry",
]

__version__ = "0.1.0"
