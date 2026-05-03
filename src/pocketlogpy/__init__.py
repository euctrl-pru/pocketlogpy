"""pocketlogpy — Log application events to PocketBase from Python."""

from ._utils import Connection, FLOW_TYPES, LOG_TYPES
from ._connect import pl_connect, pl_connect_admin
from ._setup import pl_setup
from ._flows import pl_create_flow, pl_get_flows
from ._log import pl_log, pl_success, pl_error, pl_fatal
from ._deps import (
    pl_add_dependency,
    pl_remove_dependency,
    pl_get_dependencies,
    pl_get_status,
    pl_get_dag,
)
from ._admin import pl_delete_flow, pl_delete_logs
from ._query import pl_get_logs

__all__ = [
    "Connection",
    "FLOW_TYPES",
    "LOG_TYPES",
    "pl_connect",
    "pl_connect_admin",
    "pl_setup",
    "pl_create_flow",
    "pl_get_flows",
    "pl_log",
    "pl_success",
    "pl_error",
    "pl_fatal",
    "pl_add_dependency",
    "pl_remove_dependency",
    "pl_get_dependencies",
    "pl_get_status",
    "pl_get_dag",
    "pl_delete_flow",
    "pl_delete_logs",
    "pl_get_logs",
]
