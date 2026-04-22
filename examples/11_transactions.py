"""
To run this locally:
  - Emulator: docker compose -f docker-compose.yml up -d --build
  - Env: DATASTORE_EMULATOR_HOST=localhost:10000 and GOOGLE_CLOUD_PROJECT=google-cloud-datastore-odm-dev
"""

from pathlib import Path

from dotenv import load_dotenv

from google_cloud_datastore_odm import IntegerProperty, Model, StringProperty, transaction, transactional

load_dotenv()
print("\n" + "=" * 60)
print(f"Running: {Path(__file__).name}")
print("=" * 60 + "\n")


class LedgerAccount(Model):
    name = StringProperty()
    balance = IntegerProperty(default=0)


alice = LedgerAccount(name="Alice", balance=500)
alice.put()
bob = LedgerAccount(name="Bob", balance=100)
bob.put()

print(f"[Transactional] Starting Balances -> Alice: ${alice.balance}, Bob: ${bob.balance}")

print("\n--- Context Manager ---")
try:
    # Everything inside this block is buffered in memory.
    # It commits atomically at the end of the block.
    with transaction():

        alice = LedgerAccount.get(alice.key)
        bob = LedgerAccount.get(bob.key)

        print("[Transaction] Alice pays $50")
        alice.balance -= 50
        print("[Transaction] Bob receives $50")
        bob.balance += 50

        LedgerAccount.put_multi([alice, bob])

except Exception as e:
    print(f"[Transaction] Failed: {e}")


print(f"[Transactional] Current Balances -> Alice: ${alice.balance}, Bob: ${bob.balance}")


print("\n--- Decorator (Automatic Retries on Conflict) ---")


# Datastore uses Optimistic Concurrency. If another server modifies Alice
# while this function is running, it throws an Aborted exception.
# The @transactional decorator automatically sleeps and retries!
@transactional(retries=5)
def safe_transfer(from_key, to_key, amount):
    sender = LedgerAccount.get(from_key)
    receiver = LedgerAccount.get(to_key)

    if sender.balance < amount:
        raise ValueError("Insufficient funds!")

    print(f"[Transaction] Transferring ${amount} from {sender.name} to {receiver.name}")
    sender.balance -= amount
    receiver.balance += amount

    sender.put()
    receiver.put()


safe_transfer(alice.key, bob.key, 100)

alice = LedgerAccount.get(alice.key)
bob = LedgerAccount.get(bob.key)
print(f"[Transactional] Final Balances -> Alice: ${alice.balance}, Bob: ${bob.balance}")
