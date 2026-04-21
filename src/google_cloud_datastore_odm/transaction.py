import contextvars
import functools
import inspect
import random
import time
from contextlib import contextmanager
from typing import Callable, Iterator, Optional

from google.api_core.exceptions import Aborted
from google.cloud.datastore.transaction import Transaction

from .client import get_client

_ctx_txn: contextvars.ContextVar[Optional[Transaction]] = contextvars.ContextVar(
    "google-cloud-datastore-odm-ctx-txn", default=None
)


def get_current_transaction() -> Optional[Transaction]:
    """Returns the currently active Datastore transaction, or None."""
    return _ctx_txn.get()


@contextmanager
def transaction(project: Optional[str] = None, database: Optional[str] = None) -> Iterator[Transaction]:
    """
    A context manager that starts a Datastore transaction and automatically
    routes all ODM operations (get, put, delete) through it.
    """
    client = get_client(project=project, database=database)

    if _ctx_txn.get() is not None:
        raise RuntimeError("Nested transactions are not supported by Google Cloud Datastore.")

    with client.transaction() as txn:
        token = _ctx_txn.set(txn)
        try:
            yield txn
        finally:
            _ctx_txn.reset(token)


def transactional(retries: int = 3, project: Optional[str] = None, database: Optional[str] = None) -> Callable:
    """
    Decorator that runs a function inside a Datastore transaction.
    Automatically retries the function if a concurrency conflict (Aborted) occurs.
    """

    def decorator(func: Callable) -> Callable:
        if inspect.isgeneratorfunction(func):
            raise TypeError(
                f"Cannot wrap generator function '{func.__name__}' in a transaction. "
                "Transactions must be fully resolved and cannot yield control."
            )

        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            last_exc = None

            for attempt in range(retries + 1):
                try:
                    with transaction(project=project, database=database):
                        return func(*args, **kwargs)
                except Aborted as e:
                    last_exc = e
                    if attempt < retries:
                        sleep_time = (2 ** attempt) + random.uniform(0, 1)
                        time.sleep(sleep_time)
                    continue

            raise last_exc

        return wrapper

    return decorator
