# Transactions & Concurrency

When you need to update multiple entities simultaneously—like transferring funds between two bank accounts—you must ensure the operation is **Atomic**. Either all updates succeed, or none of them do. 

Google Cloud Datastore supports fully ACID-compliant transactions, and the ODM makes them incredibly simple to use via native Python context managers and decorators. You do not need to manually pass transaction objects around; the ODM automatically routes your `.get()`, `.put()`, and `.delete()` calls.

---

## Transaction Context Manager

The simplest way to execute a transaction is using the `transaction()` context manager. When you enter the `with` block, the ODM opens a transaction. If the block executes successfully, it commits. If an exception is raised, the entire transaction is rolled back.

```python
from google_cloud_datastore_odm import Model, IntegerProperty, transaction

class LedgerAccount(Model):
    balance = IntegerProperty(default=0)

alice = LedgerAccount.get_by_id("alice")
bob = LedgerAccount.get_by_id("bob")

try:
    with transaction():
        # 1. Read from the transaction snapshot
        alice = LedgerAccount.get(alice.key)
        bob = LedgerAccount.get(bob.key)

        # 2. Mutate memory state
        alice.balance -= 50
        bob.balance += 50

        if alice.balance < 0:
            raise ValueError("Insufficient funds!")

        # 3. Buffer mutations for the commit
        LedgerAccount.put_multi([alice, bob])
        
except Exception as e:
    print(f"Transaction aborted: {e}")
```

!!! Warning "The Golden Rule: Read Before Write"
    Datastore transactions use **Snapshot Isolation**. When the transaction opens, it freezes the database state. If you `.put()` an entity inside the block, it is only buffered locally in memory. A subsequent `.query()` or `.get()` inside the same block *will not see the uncommitted entity*. 
    
    **Always perform all your reads before performing any writes!**

---

## Transactional Decorator

Datastore does not lock rows in the database when a transaction opens. Instead, it uses **Optimistic Concurrency Control**. 

If Server A and Server B both open a transaction and read Alice's account, and Server A commits first, Server B's transaction will fail with an `Aborted` exception. Server B must then restart the transaction from scratch.

To handle this gracefully, the ODM provides the `@transactional` decorator. It wraps your function in a transaction and **automatically catches `Aborted` exceptions, applying an exponential backoff sleep before retrying**.

```python
from google_cloud_datastore_odm import transactional

@transactional(retries=5)
def safe_transfer(from_id: str, to_id: str, amount: int):
    sender = LedgerAccount.get_by_id(from_id)
    receiver = LedgerAccount.get_by_id(to_id)

    if sender.balance < amount:
        raise ValueError("Insufficient funds!")

    sender.balance -= amount
    receiver.balance += amount

    sender.put()
    receiver.put()

# If another process modifies the sender concurrently, 
# this call will automatically sleep and try again up to 5 times!
safe_transfer("alice", "bob", 100)
```

!!! warning "Never yield inside a transaction"
    If you decorate a function with `@transactional`, it cannot be a generator. Yielding control back to the caller while a Datastore transaction is open can cause dangling database locks or timeout errors. The ODM will raise a `TypeError` if you attempt to wrap a generator.
