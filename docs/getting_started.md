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

Models are defined by inheriting from the `Model` class. You map Datastore fields using property descriptors.

* **`required` / `default`**: Enforces presence or provides a fallback value.
* **`choices`**: Restricts assignments to a specific list of values.
* **`repeated`**: Turns the property into a list (defaults to `[]`).
* **`indexed`**: Set to `False` to exclude massive text blocks from Datastore indexes to save space and reduce costs.
* **`name`**: Maps the Python attribute to a legacy/different Datastore column name.

```python
import datetime
from src.google_cloud_datastore_odm import (
    BytesProperty,
    BooleanProperty,
    DateProperty,
    DateTimeProperty,
    FloatProperty,
    IntegerProperty,
    JsonProperty,
    Model,
    StringProperty,
    TextProperty,
    TimeProperty,
)

class Article(Model):

    title = StringProperty(required=True)
    # Maps 'author' in Python to 'author_name' in Datastore
    author = StringProperty(required=True, name="author_name")
    status = StringProperty(default="draft", choices=["draft", "published", "archived"])
    rating = IntegerProperty(choices=[1, 2, 3, 4, 5])
    word_count = IntegerProperty(default=0)
    is_featured = BooleanProperty(default=False)
    score = FloatProperty()
    # Chronological properties with auto-population and timezone awareness
    created_at = DateTimeProperty(auto_now_add=True, tzinfo=datetime.timezone.utc)
    updated_at = DateTimeProperty(auto_now=True, tzinfo=datetime.timezone.utc)
    publish_date = DateProperty()
    publish_time = TimeProperty()
    tags = StringProperty(repeated=True)
    # Unindexed string (cannot be filtered on in queries)
    internal_notes = StringProperty(indexed=False)
    # Automatically unindexed, optionally compressed
    body = TextProperty(compressed=True)
    # Automatically unindexed, optionally compressed
    metadata: dict | list = JsonProperty()
    # Automatically unindexed, optionally compressed
    attachment_raw = BytesProperty(compressed=True)
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
from src.google_cloud_datastore_odm import Model, StringProperty, IntegerProperty, OR, or_, AND, and_, Count, Sum, Avg

class Article(Model):
    title = StringProperty(required=True)
    # The ODM automatically handles mapping this to 'author_name' in Datastore
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

# --- Fetching by Key or ID ---

fetched = Article.get(key=saved_key)
fetched_by_id = Article.get_by_id("my-first-article")

# Query filtering with raw datastore fields and operators as strings
query = Article.query().filter("author_name", "=", "Alice")
alice_articles = list(query.fetch(limit=2))

# --- ODM-Style Querying ---

# Basic Equality (Automatically maps to the 'author_name' Datastore column!)
query = Article.query().filter(Article.author == "Alice")
alice_arts = list(query.fetch(limit=10))

# Implicit AND (Multiple filters) & Inequality
implicit_and_query = Article.query().filter(Article.author == "Alice", Article.word_count > 100)

# Composite OR Logic
or_query = Article.query().filter(
    OR(Article.status == "draft", Article.rating == 5)
)

# The IN Operator (Acts as 'array-contains-any' for repeated properties)
# Supports both PEP 8 compliant lowercase and NDB legacy uppercase
in_query = Article.query().filter(Article.tags.in_(["python", "gcp"]))
IN_query = Article.query().filter(Article.tags.IN(["python", "gcp"]))

# Sorting / Ordering (Use the unary minus for descending order)
ordered_query = Article.query().filter(Article.status == "published").order(-Article.rating, Article.title)

# The NDB-style .get() method (Returns the first matching entity or None)
first_draft = Article.query().filter(Article.status == "draft").get()

# Keys-Only Queries (Extremely fast, does not download document payloads)
# Yields google.cloud.datastore.Key objects instead of Model instances
all_article_keys = list(Article.query().keys_only().fetch())

# Projection Queries (Download only specific fields to save memory/bandwidth)
# accepts Properties or raw datastore fields as strings
# Note: Accessing unprojected fields (like 'title' or 'tags') on these objects will safely raise an AttributeError.
# Attempting to .put() a projected entity will raise a RuntimeError to prevent data loss.
lightweight_articles = list(Article.query().projection(Article.author, Article.status, 'word_count').fetch())

# Distinct Queries (Get the first full document for each unique category)
# Accepts Python Property descriptors or raw Datastore field names as strings.
first_articles_by_author = list(Article.query().distinct_on(Article.author).fetch())

# Distinct + Projection (Get lightweight combinations of unique categories)
unique_author_statuses = list(Article.query().projection(
    Article.author, Article.status
).distinct_on(
    Article.author, Article.status
).fetch())

# Pagination with cursors
query = (
    Article.query()
    .order(Article.author)
    .projection(Article.author, Article.title)
    .distinct_on(Article.author)
)

cursor = None
has_more = True

while has_more:
    page, cursor, has_more = query.fetch_page(page_size=2, start_cursor=cursor)

    for article in page:
        print(f"{article.author} - {article.title}")

# Fast Server-Side Aggregations
base_query = Article.query().filter(Article.status == "published")

total_published = base_query.count()
total_words = base_query.sum(Article.word_count)
average_words = base_query.avg(Article.word_count)

# or with one RPC
stats = base_query.aggregate(
    total_articles=Count(),
    total_words=Sum(Article.word_count),
    average_words=Avg('word_count')
)

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

# Explicitly allocate a single key for this instance
draft.allocate_key()

# Reserve a batch of 5 IDs from Datastore without creating instances
reserved_keys = Article.allocate_ids(size=5)
```

## 9. Lifecycle Hooks

Models natively support NDB-style hooks (`_pre_put_hook`, `_post_get_hook`, etc.) that execute during standard and batch CRUD operations.

```python
from src.google_cloud_datastore_odm import Model, StringProperty

class TrackedTask(Model):
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


## 10. Multi-Tenancy & Dynamic Routing

Google Cloud Datastore is heavily used for multi-tenant applications. The ODM natively supports routing data to specific GCP Projects or Datastore Namespaces. You can define static routing defaults using an inner `Meta` class, or dynamically override them on the fly for specific instances or queries.

```python
from src.google_cloud_datastore_odm import Model, StringProperty

class SystemLog(Model):
    event = StringProperty()
    user_id = StringProperty()
    
    class Meta:
        # These defaults will be used unless explicitly overridden
        kind = "AuditLog"
        project = "central-logging-system"
        namespace = "default-events"
        database = 'db-1'

# Statically routed: Uses the Meta class defaults
log_default = SystemLog(event="Startup", user_id="system")
log_default.put()
print(log_default.key.namespace)  # Outputs: default-events

# Dynamically routed: Override project and namespace on the fly
# This completely bypasses the Meta defaults and routes to a custom GCP project!
log_tenant = SystemLog(
    event="Login", 
    user_id="alice", 
    project="customer-project-123", 
    namespace="tenant-b",
    database="db-2"
)
log_tenant.put()

# Querying specific projects/namespaces
# Queries the default Meta project/namespace:
central_logs = list(SystemLog.query().filter("event", "=", "Startup").fetch())

# Queries the ad-hoc customer project/namespace:
customer_logs = list(
    SystemLog.query(project="customer-project-123", namespace="tenant-b", database="db-2")
    .filter("user_id", "=", "alice")
    .fetch()
)
```
