"""
To run this locally:
  - Emulator: docker compose -f docker-compose.yml up -d --build
  - Env: DATASTORE_EMULATOR_HOST=localhost:10000 and GOOGLE_CLOUD_PROJECT=google-cloud-datastore-odm-dev
"""

import json
from pathlib import Path

from dotenv import load_dotenv

from google_cloud_datastore_odm import IntegerProperty, Model, StringProperty

load_dotenv()
print("\n" + "=" * 60)
print(f"Running: {Path(__file__).name}")
print("=" * 60 + "\n")


class ConfigItem(Model):
    key_name = StringProperty()
    value = IntegerProperty()
    environment = StringProperty(default="production")


doc = ConfigItem(key_name="max_retries", value=5)

print("--- Dictionary Reads & Writes ---")
print(f"[Dict] Read doc['key_name']: {doc['key_name']}")

doc['value'] = 10
print(f"[Dict] Write doc['value'] -> accessed via property: {doc.value}")

print("\n--- Iteration & Items ---")
print(f"[Dict] Keys iteration: {list(doc)}")
print(f"[Dict] Items iteration: {dict(doc.items())}")

print("\n--- Serialization (to_dict) ---")
print("[Dict] Full to_dict():")
print(json.dumps(doc.to_dict(), indent=2))

print("\n[Dict] to_dict(include=['key_name']):")
print(json.dumps(doc.to_dict(include=["key_name"]), indent=2))

print("\n[Dict] to_dict(exclude=['environment']):")
print(json.dumps(doc.to_dict(exclude=["environment"]), indent=2))
