# Models & Properties

The data modeling layer is the core of the ODM. It allows you to define strict schemas, enforce types, and structure your Datastore entities using clean, readable Python code.

---

## The Property Arsenal

The ODM provides a comprehensive suite of `Property` descriptors. From standard primitives to complex geospatial and embedded data, properties handle type validation and Datastore mapping automatically.

Here is a showcase of the available property types:

```python
import datetime
from google.cloud.datastore.helpers import GeoPoint
from google_cloud_datastore_odm import (
    Model, StringProperty, IntegerProperty, FloatProperty, BooleanProperty,
    TextProperty, DateTimeProperty, DateProperty, TimeProperty,
    JsonProperty, PickleProperty, BytesProperty, GenericProperty,
    KeyProperty, StructuredProperty, ComputedProperty
)

class Address(Model):
    city = StringProperty()
    country = StringProperty()

class Article(Model):
    # Primitives
    title = StringProperty(required=True)
    word_count = IntegerProperty(default=0)
    score = FloatProperty()
    is_published = BooleanProperty(default=False)
    
    # Large Text (Automatically unindexed to bypass Datastore's 1500-byte limit)
    body = TextProperty(compressed=True) 

    # Dates and Times
    created_at = DateTimeProperty(auto_now_add=True, tzinfo=datetime.timezone.utc)
    updated_at = DateTimeProperty(auto_now=True, tzinfo=datetime.timezone.utc)
    publish_date = DateProperty()

    # Complex Data Structures
    metadata = JsonProperty(compressed=True)
    raw_payload = BytesProperty()
    legacy_object = PickleProperty()
    schemaless_data = GenericProperty()

    # Relational & Structured
    author_key = KeyProperty("Author")
    location = StructuredProperty(Address)
    coordinates = GeoPtProperty()

    # Computed Properties (Evaluated dynamically, cannot be manually assigned)
    @ComputedProperty
    def read_time(self):
        return max(1, self.word_count // 200) if self.word_count else 0
```

---

## Aliasing and Legacy Databases

Often, the column names in your legacy database don't adhere to PEP-8 Python naming standards. You can easily map clean Python attributes to messy Datastore column names using the `name` argument.

Furthermore, **`key` is a strictly reserved keyword in the ODM**. If your legacy database actually has a column named `"key"`, you *must* use an alias to access it.

```python
class LegacyData(Model):
    # Python attribute is 'legacy_key', Datastore column is 'key'
    legacy_key = StringProperty(name="key")
    
    status = StringProperty(name="db_status_col")
```

When instantiating a model, you typically pass the Datastore ID via `id=...` and the parent key via `parent=...`. 

However, if your model explicitly defines properties actually named `id` or `parent`, you must prefix the routing kwargs with an underscore (`_id`, `_parent`) so the ODM knows which one is the Datastore Key routing metadata and which one is the property value:

```python
class Node(Model):
    id = StringProperty()      # An actual property
    parent = StringProperty()  # An actual property

# Creating an entity with a specific Datastore Key ID and Parent Key
doc = Node(
    _id="node-123",            # Sets Datastore Key ID
    _parent=some_parent_key,   # Sets Datastore Parent
    id="internal-id",          # Sets Python property
    parent="internal-parent"   # Sets Python property
)
```

---

## Dict style access

ODM models natively support Python's dictionary protocol. This makes it incredibly easy to integrate with web frameworks (like FastAPI or Flask) or to dynamically iterate over properties.

```python
class ConfigItem(Model):
    key_name = StringProperty()
    value = IntegerProperty()

doc = ConfigItem(key_name="max_retries", value=5)

# Dictionary read/write access
print(doc["key_name"])
doc["value"] = 10

# Iteration
for prop_name, prop_val in doc.items():
    print(f"{prop_name}: {prop_val}")
```

## Serialization

To convert a model instance into native clean Python data structures, use:

- `to_dict`: to native dict with intact types directly from model
- `to_json_dict`: to serialized dictionary where each property type has a default serializer which can be overriden using the `@field_serializer` decorator
- `to_json`: same as the above, but returns the stringified dump of the dictionary

You can specifically include or exclude fields as needed.

```python
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
    key_val=datastore.Key("TargetNode", "node-123", project="dummy-project"),
    address=Address(city="San Francisco", zip_code=94105),
    dynamic_val={"anything": "goes_here", "even_dates": datetime.date.today()}
)

# Returns pure Python objects (datetime, bytes, datastore.Key)
# We use pprint here because json.dumps would throw a TypeError!
python_dict = doc.to_dict()

# bytes become Base64, datetimes become ISO strings, etc
# custom @field_serializer decorated fields are serialized as dictated
json_dict = doc.to_json_dict()

# eeturns the final JSON encoded string
json_string = doc.to_json(include=["string_val", "dt_val", "date_val", "address"])
```

---

## Schema Introspection

Need to programmatically read your model's configuration? The ODM provides a powerful `.get_schema()` class method. 

This is incredibly useful if you want to dynamically generate GraphQL schemas, OpenAPI specs, or admin dashboards.

```python
# Returns a JSON-serializable dictionary of all property configurations
schema = Article.get_schema(output_format="full")

# Returns a dictionary mapping Python property names to Datastore column names
aliases = Article.get_schema(output_format="property_aliases")

# Returns the raw Property objects
props = Article.get_schema(output_format="properties")

# Returns a dictionary mapping Python property names to property instances
named = Article.get_schema(output_format="named_properties")
```

---

## Advanced: Pre-Allocating IDs

Sometimes you need to know an entity's ID *before* you save it to the database (for example, to use it as a parent for child entities you are constructing simultaneously).

You can request a block of guaranteed-unique integer IDs directly from Google Cloud Datastore using `.allocate_ids()`:

```python
# Reserve 3 integer IDs from the Datastore backend
reserved_keys = Article.allocate_ids(size=3)

for key in reserved_keys:
    print(f"Reserved ID: {key.id}")
```

If you have an unsaved instance and just want to assign it an ID immediately without triggering a full `.put()` operation, use `.allocate_key()`:

```python
draft = Article(title="My Draft")

# Generates and attaches an ID via RPC immediately
draft.allocate_key() 

print(draft.key.id)
```
