"""
Datastore client connection manager for the Google Cloud Datastore ODM.

This module provides a singleton pattern to ensure that only one instance 
of the `google.cloud.datastore.Client` is created and shared across the 
entire application lifecycle. This prevents connection overhead and 
memory leaks.
"""

from typing import Dict, Optional

from google.cloud import datastore

_clients: Dict[Optional[str], datastore.Client] = {}


def get_client(project: Optional[str] = None) -> datastore.Client:
    """Retrieve the global Google Cloud Datastore client instance.

    If the client for the requested project has not been initialized yet,
    this function will create a new instance. If `project` is None, it
    automatically infers the Google Cloud Project ID and credentials
    from the environment.

    Args:
        project (Optional[str]): The specific GCP project ID to connect to.

    Returns:
        datastore.Client: The active Datastore client connection.
    """
    global _clients
    if project not in _clients:
        _clients[project] = datastore.Client(project=project)
    return _clients[project]
