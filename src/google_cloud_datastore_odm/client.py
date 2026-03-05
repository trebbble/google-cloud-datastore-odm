from google.cloud import datastore

_client = None


def get_client():
    global _client
    if _client is None:
        _client = datastore.Client()
    return _client
