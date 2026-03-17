# Getting Started

This guide will walk you through the core features of the Google Cloud Datastore ODM, from defining your first schema to advanced batch operations and lifecycle hooks.

---

## 1. Prerequisites

To run these examples locally, ensure you have the Datastore Emulator running and your environment variables set. 

```bash
# Example .env configuration
DATASTORE_EMULATOR_HOST=localhost:10000
GOOGLE_CLOUD_PROJECT=google-cloud-datastore-odm-dev
```

## 2. Defining Models and Properties

Models are defined by inheriting from the `Model` class. You map Datastore fields using property descriptors like `StringProperty` and `IntegerProperty`.

* **`__kind__`**: Customizes the Datastore kind (defaults to the class name).
* **`required` / `default`**: Enforces presence or provides a fallback value.
* **`choices`**: Restricts assignments to a specific list of values.
* **`repeated`**: Turns the property into a list (defaults to `[]`).
* **`indexed`**: Set to `False` to exclude massive text blocks from Datastore indexes to save space and reduce costs.
* **`name`**: Maps the Python attribute to a legacy/different Datastore column name.

```python
from src.google_cloud_datastore_odm import IntegerProperty, Model, StringProperty

class Article(Model):
    __kind__ = "Article"

    title = StringProperty(required=True)
    
    # Maps 'author' in Python to 'author_name' in Datastore
    author = StringProperty(required=True, name="author_name")

    status = StringProperty(default="draft", choices=["draft", "published", "archived"])
    rating = IntegerProperty(choices=[1, 2, 3, 4, 5])
    word_count = IntegerProperty(default=0)
    tags = StringProperty(repeated=True)

    # Unindexed property (cannot be filtered on in queries)
    internal_notes = StringProperty(indexed=False)
```

## 3. Validation

The ODM provides three distinct layers of validation to ensure bad data never reaches your database.

### Inline Property Validators
Passed directly to the property definition. They run first.
```python
from src.google_cloud_datastore_odm import Model, StringProperty

def no_emoji_allowed(value: str) -> str:
    for char in value:
        if ord(char) > 127:
            raise ValueError(f"Value '{value}' contains non-ASCII characters")
    return value

class Comment(Model):
    body = StringProperty(required=True, validators=[no_emoji_allowed])
```

### Field-Level Validators
Decorated with `@field_validator('property_name')`. These run automatically during property assignment.
```python
from src.google_cloud_datastore_odm import Model, StringProperty, IntegerProperty, field_validator

class Article(Model):
    title = StringProperty(required=True)
    author = StringProperty(required=True, name="author_name")
    status = StringProperty(default="draft", choices=["draft", "published", "archived"])
    rating = IntegerProperty(choices=[1, 2, 3, 4, 5])
    word_count = IntegerProperty(default=0)
    tags = StringProperty(repeated=True)
    internal_notes = StringProperty(indexed=False)

    @field_validator('title')
    def validate_title(self, value: str) -> str:
        if len(value) < 3 or len(value) > 200:
            raise ValueError("Title must be between 3 and 200 characters.")
        return value
```

### Model-Level Validators
Decorated with `@model_validator`. These run right before `put` operations are called, right before any pre-put hooks,
and are used for cross-property logic.
```python
from src.google_cloud_datastore_odm import Model, StringProperty, IntegerProperty, model_validator

class Article(Model):
    title = StringProperty(required=True)
    author = StringProperty(required=True, name="author_name")
    status = StringProperty(default="draft", choices=["draft", "published", "archived"])
    rating = IntegerProperty(choices=[1, 2, 3, 4, 5])
    word_count = IntegerProperty(default=0)
    tags = StringProperty(repeated=True)
    internal_notes = StringProperty(indexed=False)

    @model_validator
    def validate_published_requires_content(self):
        if self.status == "published" and (self.word_count or 0) == 0:
            raise ValueError("A published article must have a word count > 0")
```

## 4. Creating and Saving Entities

You can create instances using standard keyword arguments. To explicitly set a custom string ID, use the `id` shortcut.

```python
from src.google_cloud_datastore_odm import Model, StringProperty, IntegerProperty

class Article(Model):
    title = StringProperty(required=True)
    author = StringProperty(required=True, name="author_name")
    status = StringProperty(default="draft", choices=["draft", "published", "archived"])
    rating = IntegerProperty(choices=[1, 2, 3, 4, 5])
    word_count = IntegerProperty(default=0)
    tags = StringProperty(repeated=True)
    internal_notes = StringProperty(indexed=False)

# Create with explicit string ID
article = Article(
    id="my-first-article",
    title="Hello, World!",
    author="Alice",
    word_count=500,
    tags=["python", "odm"]
)

# Access dictionary-style
article['status'] = "published"

# Save to Datastore
saved_key = article.put()
print(f"Saved with ID: {article.key.id_or_name}")
```

## 5. Fetching and Querying

The ODM provides familiar NDB-style methods for retrieving data.

```python
from src.google_cloud_datastore_odm import Model, StringProperty, IntegerProperty

class Article(Model):
    title = StringProperty(required=True)
    author = StringProperty(required=True, name="author_name")
    status = StringProperty(default="draft", choices=["draft", "published", "archived"])
    rating = IntegerProperty(choices=[1, 2, 3, 4, 5])
    word_count = IntegerProperty(default=0)
    tags = StringProperty(repeated=True)
    internal_notes = StringProperty(indexed=False)

article = Article(
    id="my-first-article",
    title="Hello, World!",
    author="Alice",
    word_count=500,
    tags=["python", "odm"]
)

saved_key = article.put()

# Fetch by Key
fetched = Article.get(key=saved_key)

# Fetch by explicit ID
fetched_by_id = Article.get_by_id("my-first-article")

# Query filtering
# Note: Currently, filters must use the underlying Datastore alias name
query = Article.query().filter("author_name", "=", "Alice")
results = list(query.fetch(limit=2))
```

## 6. Strict Equality

Instances are strictly compared. For two instances to be equal (`==`), they must have the exact same Datastore `Key` **and** their underlying unsaved memory states must match perfectly.

```python
from src.google_cloud_datastore_odm import Model, StringProperty, IntegerProperty

class Article(Model):
    title = StringProperty(required=True)
    author = StringProperty(required=True, name="author_name")
    status = StringProperty(default="draft", choices=["draft", "published", "archived"])
    rating = IntegerProperty(choices=[1, 2, 3, 4, 5])
    word_count = IntegerProperty(default=0)
    tags = StringProperty(repeated=True)
    internal_notes = StringProperty(indexed=False)

article = Article(
    id="my-first-article",
    title="Hello, World!",
    author="Alice",
    word_count=500,
    tags=["python", "odm"]
)

saved_key = article.put()
fetched = Article.get(key=saved_key)
fetched_by_id = Article.get_by_id("my-first-article")

print(fetched == fetched_by_id) # True

# Modify one's memory state
fetched_by_id.title = "A New Title in Memory"

print(fetched == fetched_by_id) # False (Memory state drifted)
```

## 7. Batch Operations

Batch operations execute in a single RPC call, saving massive amounts of network overhead.

```python
from src.google_cloud_datastore_odm import Model, StringProperty, IntegerProperty

class Article(Model):
    title = StringProperty(required=True)
    author = StringProperty(required=True, name="author_name")
    status = StringProperty(default="draft", choices=["draft", "published", "archived"])
    rating = IntegerProperty(choices=[1, 2, 3, 4, 5])
    word_count = IntegerProperty(default=0)
    tags = StringProperty(repeated=True)
    internal_notes = StringProperty(indexed=False)

batch_articles = [
    Article(title="Batch 1", author="System", word_count=100),
    Article(title="Batch 2", author="System", word_count=200),
]

# Save multiple entities at once
batch_keys = Article.put_multi(batch_articles)

# Fetch multiple entities at once (preserves order, handles missing keys)
fetched_batch = Article.get_multi(batch_keys)

# Delete multiple entities at once
Article.delete_multi(batch_keys)
```

## 8. Key Management & Aliasing

### Legacy Column Names & Reserved Words
If you need to map to a legacy column actually named "key" or "id" in Datastore, define the Python property safely and use the `name=` parameter. Provide explicit routing info using the `_` prefix.

```python
from src.google_cloud_datastore_odm import Model, StringProperty, IntegerProperty
class LegacyDataModel(Model):
    id = IntegerProperty() # your business logic ID
    legacy_key = StringProperty(name='key') # alias for actual Datastore field called 'key' ; 'key' attribute is reserved

# Route Datastore ID using _id alias, assign the field `key` using legacy_key alias
instance = LegacyDataModel(_id="123", id=1, legacy_key="some-string-data")
```

### Allocating IDs
You can manually reserve blocks of IDs from the Datastore before creating your objects.

```python
from src.google_cloud_datastore_odm import Model, StringProperty, IntegerProperty

class Article(Model):
    title = StringProperty(required=True)
    author = StringProperty(required=True, name="author_name")
    status = StringProperty(default="draft", choices=["draft", "published", "archived"])
    rating = IntegerProperty(choices=[1, 2, 3, 4, 5])
    word_count = IntegerProperty(default=0)
    tags = StringProperty(repeated=True)
    internal_notes = StringProperty(indexed=False)

draft = Article(title="Draft", author="Carol")
print(draft.has_complete_key) # False

# Explicitly allocate a single key for this instance
draft.allocate_key()
print(draft.has_complete_key) # True

# Reserve a batch of 5 IDs from Datastore without creating instances
reserved_keys = Article.allocate_ids(size=5)
```

## 9. Lifecycle Hooks

Models natively support NDB-style hooks (`_pre_put_hook`, `_post_get_hook`, etc.) that execute during standard and batch CRUD operations.

```python
from src.google_cloud_datastore_odm import Model, StringProperty

class TrackedTask(Model):
    __kind__ = "TrackedTask"
    description = StringProperty()

    def _pre_put_hook(self):
        print(f"Preparing to save: {self.description}")

    def _post_put_hook(self):
        print(f"Successfully saved with ID: {self.key.id_or_name}")

    @classmethod
    def _pre_get_hook(cls, key):
        print(f"Preparing to fetch key: {key.id_or_name}")

    @classmethod
    def _post_get_hook(cls, key, instance):
        print(f"Fetched key. Found instance? {instance is not None}")

# Hooks will fire automatically
task = TrackedTask(description="Learn Python ODM")
task_key = task.put() 
fetched_task = TrackedTask.get(task_key)
```
