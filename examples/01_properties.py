"""
To run this locally:
  - Emulator: docker compose -f docker-compose.yml up -d --build
  - Env: DATASTORE_EMULATOR_HOST=localhost:10000 and GOOGLE_CLOUD_PROJECT=google-cloud-datastore-odm-dev
"""

import datetime
from pathlib import Path

from dotenv import load_dotenv
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
)

load_dotenv()
print("\n" + "=" * 60)
print(f"Running: {Path(__file__).name}")
print("=" * 60 + "\n")


class Address(Model):
    city = StringProperty()
    country = StringProperty()


class Author(Model):
    name = StringProperty()


class ShowcaseModel(Model):
    # string types
    title = StringProperty(required=True)  # required
    legacy_name = StringProperty(name="db_legacy_name")  # Datastore field alias
    status = StringProperty(default="draft", choices=["draft", "published"])  # choices and default
    tags = StringProperty(repeated=True)  # repeated
    internal_notes = StringProperty(indexed=False)  # unindexed
    body = TextProperty()  # Automatically unindexed

    # numeric types
    score = FloatProperty()
    is_featured = BooleanProperty(default=False)
    word_count = IntegerProperty(default=0)

    # date
    created_at = DateTimeProperty(auto_now_add=True, tzinfo=datetime.timezone.utc)  # auto on creation
    updated_at = DateTimeProperty(auto_now=True, tzinfo=datetime.timezone.utc)  # auto on mutation
    publish_date = DateProperty()
    publish_time = TimeProperty()

    # geospatial
    coordinates = GeoPtProperty()

    # complex schemaless
    attachment = BytesProperty(compressed=True)  # compressed
    metadata = JsonProperty()
    python_object = PickleProperty(compressed=True)
    dynamic_payload = GenericProperty()

    # relational
    author_key = KeyProperty(kind=Author)

    # structured complex
    location = StructuredProperty(Address)

    # Computed
    @ComputedProperty
    def read_time(self):
        return max(1, self.word_count // 200) if self.word_count else 0


print("[ShowcaseModel] Initializing entity with all property types...")
author = Author(name="Alice").put()

entity = ShowcaseModel(
    title="ODM Showcase",
    legacy_name="Old DB Entry",
    status="published",
    tags=["python", "odm"],
    internal_notes="Do not index this",
    score=9.9,
    is_featured=True,
    word_count=450,
    publish_date=datetime.date.today(),
    publish_time=datetime.datetime.now(datetime.timezone.utc).time(),
    attachment=b"raw bytes",
    body="A massive block of unindexed text...",
    metadata={"version": 1, "features": ["typed"]},
    python_object={"set", "of", "items"},
    dynamic_payload=[1, "two", {"three": 3}],
    author_key=author,
    location=Address(city="Athens", country="Greece"),
    coordinates=GeoPoint(37.9838, 23.7275)
)
entity.put()

print(f"[ShowcaseModel] Entity saved successfully. Key ID: {entity.key.id_or_name}")
print(f"[ShowcaseModel] Auto-populated created_at: {entity.created_at}")
print(f"[ShowcaseModel] Computed read_time: {entity.read_time} minutes")
print(f"[ShowcaseModel] Embedded location city: {entity.location.city}")
print(f"[ShowcaseModel] GeoPt coordinates: {entity.coordinates.latitude}, {entity.coordinates.longitude}")
print(f"[ShowcaseModel] Python Pickle restored type: {type(entity.python_object)}")
print(f"[ShowcaseModel] Total repr: {entity}")
