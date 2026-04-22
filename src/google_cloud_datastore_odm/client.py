"""Datastore client connection manager for the Google Cloud Datastore ODM.

This module provides a singleton pattern to ensure that only one instance
of the `google.cloud.datastore.Client` is created per GCP project and database.
This prevents connection overhead and memory leaks.
"""

from google.cloud import datastore

_clients: dict[tuple[str | None, str | None], datastore.Client] = {}


def get_client(project: str | None = None, database: str | None = None) -> datastore.Client:
    """Retrieve the global Google Cloud Datastore client instance.

    If the client for the requested project and database has not been initialized yet,
    this function will create and cache a new instance. If `project` or `database`
    is `None`, it automatically infers the defaults from the host environment
    (e.g., the `GOOGLE_CLOUD_PROJECT` environment variable).

    Args:
        project (str | None): The specific GCP project ID to connect to. Defaults to `None`.
        database (str | None): The specific Datastore database name to connect to. Defaults to `None`.

    Returns:
        datastore.Client: The active Datastore client connection.

    Examples:
        Retrieve the default client inferred from the environment:
        ```python
        from google_cloud_datastore_odm.client import get_client

        client = get_client()
        ```

        Retrieve a client for a specific tenant database:
        ```python
        tenant_client = get_client(project="my-project", database="tenant-db")
        ```
    """
    global _clients
    cache_key = (project, database)

    if cache_key not in _clients:
        _clients[cache_key] = datastore.Client(project=project, database=database)

    return _clients[cache_key]
