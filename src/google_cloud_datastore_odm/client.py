"""
Datastore client connection manager for the Google Cloud Datastore ODM.

This module provides a singleton pattern to ensure that only one instance 
of the `google.cloud.datastore.Client` is created per GCP project and database.
This prevents connection overhead and memory leaks.
"""

from typing import Dict, Optional, Tuple

from google.cloud import datastore

_clients: Dict[Tuple[Optional[str], Optional[str]], datastore.Client] = {}


def get_client(project: Optional[str] = None, database: Optional[str] = None) -> datastore.Client:
    """Retrieve the global Google Cloud Datastore client instance.

    If the client for the requested project/database has not been initialized yet,
    this function will create a new instance. If `project` or `database` is None, it
    automatically infers the defaults from the environment.

    Args:
        project (Optional[str]): The specific GCP project ID to connect to.
        database (Optional[str]): The specific Datastore database name to connect to.

    Returns:
        datastore.Client: The active Datastore client connection.
    """
    global _clients
    cache_key = (project, database)

    if cache_key not in _clients:
        _clients[cache_key] = datastore.Client(project=project, database=database)

    return _clients[cache_key]
