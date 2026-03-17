"""
Datastore client connection manager for the Google Cloud Datastore ODM.

This module provides a singleton pattern to ensure that only one instance 
of the `google.cloud.datastore.Client` is created and shared across the 
entire application lifecycle. This prevents connection overhead and 
memory leaks.
"""

from typing import Optional

from google.cloud import datastore

_client: Optional[datastore.Client] = None


def get_client() -> datastore.Client:
    """Retrieve the global Google Cloud Datastore client instance.

    If the client has not been initialized yet, this function will create a new
    instance. It automatically infers the Google Cloud Project ID and credentials
    from the environment (e.g., `GOOGLE_CLOUD_PROJECT`, `GOOGLE_APPLICATION_CREDENTIALS`, 
    or the Datastore Emulator host).

    Subsequent calls will return the cached singleton instance.

    Returns:
        datastore.Client: The active Datastore client connection.

    Example:
        ```python
        from google_cloud_datastore_odm.client import get_client

        # Access the raw GCP client if you need to bypass the ODM
        client = get_client()
        query = client.query(kind="RawKind")
        ```
    """
    global _client
    if _client is None:
        _client = datastore.Client()
    return _client
