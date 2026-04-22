"""
To run this locally:
  - Emulator: docker compose -f docker-compose.yml up -d --build
  - Env: DATASTORE_EMULATOR_HOST=localhost:10000 and GOOGLE_CLOUD_PROJECT=google-cloud-datastore-odm-dev
"""

import json
from pathlib import Path

from dotenv import load_dotenv

from google_cloud_datastore_odm import BooleanProperty, IntegerProperty, Model, StringProperty

load_dotenv()
print("\n" + "=" * 60)
print(f"Running: {Path(__file__).name}")
print("=" * 60 + "\n")


class UserAccount(Model):
    username = StringProperty(required=True, name="db_username")
    age = IntegerProperty(default=18)
    is_active = BooleanProperty(default=True)
    tags = StringProperty(repeated=True)


print("[Introspection] Python Class Name: UserAccount")
print(f"[Introspection] Datastore Kind: {UserAccount.kind()}")

print("\n--- Full Schema Output ---")
# Returns a JSON-serializable dict of all configurations
print(json.dumps(UserAccount.get_schema(output_format="full"), indent=2))

print("\n--- Property Instances ---")
# Returns actual Property objects
props = UserAccount.get_schema(output_format="properties")
print(f"[Introspection] Found {len(props)} Property instances:")

print("\n--- Named Properties ---")
# Returns Dict[python_name, Property]
named = UserAccount.get_schema(output_format="named_properties")
print(json.dumps(named, indent=2, default=str))

print("\n--- Property Aliases ---")
# Returns mapping of Python names to Datastore names
print(json.dumps(UserAccount.get_schema(output_format="property_aliases"), indent=2))
