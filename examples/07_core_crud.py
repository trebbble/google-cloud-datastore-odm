"""
To run this locally:
  - Emulator: docker compose -f docker-compose.yml up -d --build
  - Env: DATASTORE_EMULATOR_HOST=localhost:10000 and GOOGLE_CLOUD_PROJECT=google-cloud-datastore-odm-dev
"""

import datetime
from pathlib import Path

from dotenv import load_dotenv

from google_cloud_datastore_odm import DateTimeProperty, Model, StringProperty

load_dotenv()
print("\n" + "=" * 60)
print(f"Running: {Path(__file__).name}")
print("=" * 60 + "\n")


class Note(Model):
    text = StringProperty()
    created_at = DateTimeProperty(auto_now_add=True, tzinfo=datetime.timezone.utc)
    updated_at = DateTimeProperty(auto_now=True, tzinfo=datetime.timezone.utc)


print("--- Single Operations ---")
note = Note(id="my-note", text="Hello World")
saved_key = note.put()
print(f"[CRUD] Saved single entity: {saved_key}")

fetched_by_key = Note.get(saved_key)
fetched_by_id = Note.get_by_id("my-note")
print(f"[CRUD] Fetched by Key: {fetched_by_key}")
print(f"[CRUD] Fetched by ID:  {fetched_by_id}")

print("\n--- Memory State & Equality (__eq__) ---")
print(f"[Equality] Is fetched_by_key == fetched_by_id? {fetched_by_key == fetched_by_id}")
print(f"[CRUD] fetched_by_key with ID '{fetched_by_key.key.id_or_name}', "
      f"created at {fetched_by_key.created_at}, "
      f"updated at {fetched_by_key.updated_at}")
print(f"[CRUD] fetched_by_id with ID '{fetched_by_id.key.id_or_name}', "
      f"created at {fetched_by_id.created_at}, "
      f"updated at {fetched_by_id.updated_at}")


fetched_by_key.text = "Changed in memory"
print(f"[Equality] Are they equal after memory mutation? {fetched_by_key == fetched_by_id}")

fetched_by_key.put()
print(f"[CRUD] Entity with ID '{fetched_by_key.key.id_or_name}', "
      f"created at {fetched_by_key.created_at}, "
      f"updated at {fetched_by_key.updated_at}")

fetched_by_key.delete()
print("[CRUD] Deleted single entity.")
fetched_by_id = Note.get_by_id("my-note")
print(f"[CRUD] Fetched by ID:  {fetched_by_id}")

print("\n--- Batch Operations (Multi) ---")
batch = [
    Note(text="Batch 1"),
    Note(text="Batch 2"),
    Note(text="Batch 3")
]

batch_keys = Note.put_multi(batch)
print(f"[Batch] Saved {len(batch_keys)} entities in one RPC call.")

fetched_batch = Note.get_multi(batch_keys)
print(f"[Batch] Fetched {len(fetched_batch)} entities:")
for entity in fetched_batch:
    entity: Note
    print(f"Entity with ID '{entity.key.id_or_name}' created at {entity.created_at}")

Note.delete_multi(batch_keys)
print(f"[Batch] Deleted {len(batch_keys)} entities in one RPC call.")

notes = list(Note.query().fetch())
print(f"[Batch] Fetched {len(notes)} entities")
