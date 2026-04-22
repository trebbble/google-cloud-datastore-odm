"""
To run this locally:
  - Emulator: docker compose -f docker-compose.yml up -d --build
  - Env: DATASTORE_EMULATOR_HOST=localhost:10000 and GOOGLE_CLOUD_PROJECT=google-cloud-datastore-odm-dev
"""

from pathlib import Path

from dotenv import load_dotenv

from google_cloud_datastore_odm import Model, StringProperty

load_dotenv()
print("\n" + "=" * 60)
print(f"Running: {Path(__file__).name}")
print("=" * 60 + "\n")

print("--- Reserved Property Names ---")
try:
    class BadModel(Model):
        key = StringProperty()  # 'key' is strictly reserved by the ODM
except ValueError as e:
    print(f"[Caught] Model definition error: {e}")


print("\n--- Explicit IDs, Parents, and Aliased Kwargs ---")


class LegacyData(Model):
    # To map to a Datastore column literally named 'key', use an alias:
    legacy_key = StringProperty(name="key")

    # We have actual properties named 'id' and 'parent'
    id = StringProperty()
    parent = StringProperty()


parent_key = LegacyData.key_from_id("parent-node")

# Because our model has properties called 'id' and 'parent', we must use
# the `_id` and `_parent` kwargs to configure the actual Datastore Key!
doc = LegacyData(
    _id="custom-explicit-id",
    _parent=parent_key,
    legacy_key="db_value",
    id="python_property_value",
    parent="python_property_value"
)
doc.put()

print(f"[LegacyData] Datastore Key ID: {doc.key.id_or_name}")
print(f"[LegacyData] Datastore Parent ID: {doc.key.parent.id_or_name}")
print(f"[LegacyData] Python 'id' property value: {doc.id}")
print(f"[LegacyData] Python 'legacy_key' property value: {doc.legacy_key}")

print("\n--- Repr and Identification ---")
print(f"[Repr] String representation: {doc}")

print("\n--- Key/ID Allocation ---")
bare_doc = LegacyData(_id="will-get-id")
print(f"[Allocation] Bare doc has complete key? {not bare_doc.key.is_partial}")

print("[Allocation] Allocating 3 bare IDs from Google Datastore:")
reserved_keys = LegacyData.allocate_ids(size=3)
for k in reserved_keys:
    print(f"  - Reserved ID: {k.id}")

draft = LegacyData(legacy_key="draft")
draft.allocate_key()
print(f"[Allocation] Allocated key for specific instance before put: {draft.key}")
draft_key = draft.put()
print(f"[Allocation] After put key: {draft.key}, Returned key: {draft_key}, ID: {draft.key.id_or_name}")
