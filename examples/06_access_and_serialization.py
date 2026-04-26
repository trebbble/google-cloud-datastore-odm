"""
To run this locally:
  - Emulator: docker compose -f docker-compose.yml up -d --build
  - Env: DATASTORE_EMULATOR_HOST=localhost:10000 and GOOGLE_CLOUD_PROJECT=google-cloud-datastore-odm-dev
"""

import datetime
import json
from pathlib import Path
from pprint import pprint

from dotenv import load_dotenv
from google.cloud import datastore
from google.cloud.datastore.helpers import GeoPoint

from google_cloud_datastore_odm import (
    BooleanProperty,
    BytesProperty,
    ComputedProperty,
    DateProperty,
    DateTimeProperty,
    FloatProperty,
    GenericProperty,
    GeoPtProperty,
    IntegerProperty,
    JsonProperty,
    KeyProperty,
    Model,
    PickleProperty,
    StringProperty,
    StructuredProperty,
    TextProperty,
    TimeProperty,
    field_serializer,
)

load_dotenv()
print("\n" + "=" * 60)
print(f"Running: {Path(__file__).name}")
print("=" * 60 + "\n")


# ==========================================
# 1. Define the Models
# ==========================================

class Address(Model):
    city = StringProperty()
    zip_code = IntegerProperty()


class ComplexEntity(Model):
    # Standard Primitives
    string_val = StringProperty()
    int_val = IntegerProperty()
    bool_val = BooleanProperty()
    float_val = FloatProperty()

    # Large/Complex Data
    text_val = TextProperty(compressed=True)
    json_val = JsonProperty()
    bytes_val = BytesProperty()
    pickle_val = PickleProperty()

    # Chronological Types
    dt_val = DateTimeProperty(tzinfo=datetime.timezone.utc)
    date_val = DateProperty()
    time_val = TimeProperty()

    # Datastore Specific Types
    geo_val = GeoPtProperty()
    key_val = KeyProperty()

    # Embedded Models & Dynamic Types
    address = StructuredProperty(Address)
    dynamic_val = GenericProperty()

    # Computed Property (Calculated on the fly)
    @ComputedProperty
    def summary(self):
        return f"{self.string_val} - {self.int_val}" if self.string_val else "Empty"

    # Custom Serializer (Overrides default ISO format for to_json)
    @field_serializer("date_val")
    def format_custom_date(self, value: datetime.date) -> str:
        if value is None:
            return None
        # Return a custom formatted string instead of the default ISO format
        return value.strftime("%B %d, %Y")


# ==========================================
# 2. Instantiate and Populate
# ==========================================

# Create a mock datastore key for demonstration
mock_key = datastore.Key("TargetNode", "node-123", project="dummy-project")

doc = ComplexEntity(
    string_val="Test Entity",
    int_val=42,
    bool_val=True,
    float_val=3.14159,
    text_val="A very long text block that gets compressed.",
    json_val={"nested": {"key": "value"}, "list": [1, 2, 3]},
    bytes_val=b"raw binary data",
    pickle_val={"apple", "banana", "cherry"},  # A Python Set
    dt_val=datetime.datetime(2025, 4, 26, 12, 30, tzinfo=datetime.timezone.utc),
    date_val=datetime.date(2025, 4, 26),
    time_val=datetime.time(12, 30),
    geo_val=GeoPoint(37.7749, -122.4194),
    key_val=mock_key,
    address=Address(city="San Francisco", zip_code=94105),
    dynamic_val={"anything": "goes_here", "even_dates": datetime.date.today()}
)

# ==========================================
# 3. Serialization Demonstrations
# ==========================================

print("--- 1. Dictionary Reads & Writes ---")
print(f"Read doc['string_val']: {doc['string_val']}")
doc['int_val'] = 99
print(f"Write doc['int_val'] -> accessed via property: {doc.int_val}")

print("\n--- 2. RAW to_dict() ---")
print("Returns pure Python objects (datetime, bytes, datastore.Key).")
print("Attempting to run json.dumps() on this would crash, using pprint here.")
print("-" * 30)
# We use pprint here because json.dumps would throw a TypeError!
pprint(doc.to_dict())


print("\n--- 3. JSON-SAFE to_json_dict() ---")
print("Perfect for FastAPI/Flask. Converts all complex types to JSON-safe primitives.")
print("Notice how the bytes became Base64, datetimes became ISO strings, and the")
print("custom @field_serializer formatted the 'date_val'.")
print("-" * 30)
json_dict = doc.to_json_dict()
print(json.dumps(json_dict, indent=2))


print("\n--- 4. FULL to_json() ---")
print("Returns the final JSON encoded string. Perfect for Redis caching or logging.")
print("-" * 30)
json_string = doc.to_json(include=["string_val", "dt_val", "date_val", "address"])
print(json_string)
