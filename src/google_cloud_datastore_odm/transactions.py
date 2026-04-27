"""
Transaction management and concurrency control for the Google Cloud Datastore ODM.

This module provides context managers and decorators to orchestrate ACID-compliant 
transactions. It utilizes Python `contextvars` to automatically route all ODM 
model operations (like `.get()`, `.put()`, and queries) through the active 
transaction without requiring developers to manually pass connection objects.
"""

import contextvars
import functools
import inspect
import random
import time
from collections.abc import Callable, Iterator
from contextlib import contextmanager

from google.api_core.exceptions import Aborted
from google.cloud.datastore.transaction import Transaction

from .client import get_client

_ctx_txn: contextvars.ContextVar[Transaction | None] = contextvars.ContextVar(
    "google-cloud-datastore-odm-ctx-txn", default=None
)


def get_current_transaction() -> Transaction | None:
    """Retrieve the currently active Datastore transaction, if any.

    This function is used internally by ODM Models and Queries to determine 
    if they should route their RPC calls through an ongoing transaction snapshot.

    Returns:
        Transaction | None: The active `google.cloud.datastore.Transaction`, 
            or `None` if execution is currently outside a transaction block.
    """
    return _ctx_txn.get()


@contextmanager
def transaction(project: str | None = None, database: str | None = None) -> Iterator[Transaction]:
    """A context manager that scopes a Datastore transaction.

    When entered, this context manager requests a transaction ID from the Datastore 
    backend. Any ODM `.get()`, `.put()`, `.delete()`, or `.query()` operations 
    executed inside the `with` block will automatically bind to this transaction.

    **⚠️ Snapshot Isolation Rule (Read-Before-Write):**
    Datastore transactions use Snapshot Isolation. When the transaction opens, 
    it freezes the database state. If you `.put()` an entity inside the block, 
    it is only buffered locally in memory. A subsequent `.query()` or `.get()` 
    inside the same block *will not see the uncommitted entity*. Always perform 
    all reads before performing any writes.

    Args:
        project (str | None): The specific GCP project to run the transaction against. 
            If omitted, defaults to the environment configuration.
        database (str | None): The specific Datastore database to run the transaction against.

    Yields:
        Transaction: The raw Datastore transaction object, in case manual SDK bypass is needed.

    Raises:
        RuntimeError: If called from within an already active transaction (nested 
            transactions are strictly prohibited by Google Cloud Datastore).

    Examples:
        Safe Read-Modify-Write pattern:
        ```python
        with transaction():
            # 1. Read from the snapshot
            alice = Account.get(alice_key)
            bob = Account.get(bob_key)

            # 2. Modify memory state
            alice.balance -= 50
            bob.balance += 50

            # 3. Buffer mutations for commit
            Account.put_multi([alice, bob])
        ```
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


def transactional(retries: int = 3, project: str | None = None, database: str | None = None) -> Callable:
    """Decorator that wraps a function in a Datastore transaction with automatic retries.

    Because Datastore utilizes Optimistic Concurrency, transactions do not lock rows. 
    Instead, if another process modifies your entities while your transaction is open, 
    your commit will fail and raise an `Aborted` exception.

    This decorator catches `Aborted` exceptions, applies an exponential backoff 
    sleep (with jitter), and re-executes the function automatically. 

    Args:
        retries (int): The maximum number of retry attempts before giving up and 
            raising the `Aborted` exception to the caller. Defaults to 3.
        project (str | None): The specific GCP project override.
        database (str | None): The specific Datastore database override.

    Returns:
        Callable: The decorated function.

    Raises:
        ValueError: If the retries count is less than 0.
        TypeError: If the decorated function is a generator (yielding from inside
            a transaction causes dangling database locks).
        google.api_core.exceptions.Aborted: If all retry attempts are exhausted.
    """
    if retries < 0:
        raise ValueError("The 'retries' argument must be greater than or equal to 0.")

    def decorator(func: Callable) -> Callable:
        if inspect.isgeneratorfunction(func):
            raise TypeError(
                f"Cannot wrap generator function '{func.__name__}' in a transaction. "
                "Transactions must be fully resolved and cannot yield control."
            )

        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            attempt = 0

            while True:
                try:
                    with transaction(project=project, database=database):
                        return func(*args, **kwargs)
                except Aborted as e:
                    if attempt >= retries:
                        raise e

                    sleep_time = (2 ** attempt) + random.uniform(0, 1)
                    time.sleep(sleep_time)
                    attempt += 1

        return wrapper

    return decorator
