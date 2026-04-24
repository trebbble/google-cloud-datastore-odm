# Migration from google-cloud-ndb

If you are coming from the legacy App Engine `ndb` or `google-cloud-ndb` libraries, you will feel right at home. This ODM was built to preserve the developer ergonomics of NDB while fully embracing modern Python 3 features (like strict type hinting, context managers, and AST-based AST query building).

However, because this library is built on top of the modern `google-cloud-datastore` SDK, some legacy NDB behaviors have been dropped or reimagined. Here is everything you need to know to transition smoothly.

---

## 1. The Context Cache is Gone

**NDB Behavior:** NDB heavily relied on an implicit, thread-local context cache. If you called `.get()` on the same key twice in a request, NDB magically intercepted the second call and returned it from memory without hitting the database. You had to carefully manage `ndb.get_context().clear_cache()` to avoid stale data.

**New ODM Behavior:** There is no implicit magic cache. A `.get()` or `.fetch()` call *always* results in a Datastore network request (unless buffered inside an active transaction). 
* **Why?** Implicit caching in modern async web frameworks (like FastAPI) often leads to dangerous cross-request data leaks. 
* **The Fix:** If you need caching, implement it explicitly at your application layer (e.g., using Redis or Python's `@lru_cache`). *(Note: A modern distributed cache hook is planned for the roadmap).*

---

## 2. Model Configuration (`Meta` vs `_get_kind`)

**NDB Behavior:** To override a Datastore Kind, you overrode the `@classmethod def _get_kind(cls)`. To route to a different namespace, you had to globally change the NDB context.

**New ODM Behavior:** Configuration is now declarative via the inner `Meta` class. You can configure Kinds, Namespaces, Databases, and Projects securely at the model level.

```python
# --- OLD NDB ---
class User(ndb.Model):
    @classmethod
    def _get_kind(cls):
        return 'LegacyUser'

# --- NEW ODM ---
class User(Model):
    class Meta:
        kind = 'LegacyUser'
        project = 'different-project'
        database = 'some-db'
        namespace = 'tenant-a'
```

---

## 3. Property Deprecations & Upgrades

Most properties map 1:1, but several App Engine-specific properties have been dropped or modernized.

### Renamed / Upgraded
* `ndb.BlobProperty` ➡️ Use `BytesProperty`.
* `ndb.StringProperty(indexed=False)` ➡️ Use `TextProperty()`. (Text properties are unindexed by default to bypass the 1500-byte limit).

### The `compressed=True` Superpower
NDB had specific classes like `ndb.CompressedTextProperty`. The new ODM simplifies this by exposing a `compressed=True` argument across multiple data types. This natively zlib-compresses the payload before saving it to Datastore.
Supported on: `TextProperty`, `JsonProperty`, `BytesProperty`, `PickleProperty`, and `GenericProperty`.

### Dropped Properties
* **`UserProperty`:** The App Engine Users API has been dead for years. Use a standard `StringProperty` to store the user's ID or email.
* **`BlobKeyProperty`:** The App Engine Blobstore API is dead. Use `StringProperty` to store standard Google Cloud Storage URIs.
* **`LocalStructuredProperty`:** Dropped in favor of standard `StructuredProperty` (which embeds the model) or `JsonProperty` (which stores schema-less dicts).

---

## 4. Validation

**NDB Behavior:** To validate data, you either wrote custom property subclasses or used the `validator=` argument in the property constructor. To validate across multiple fields, you often had to hack the `_pre_put_hook`.

**New ODM Behavior:** The new ODM provides a validation pipeline using inline validators along with decorators in two levels and hooks. 

* **`@field_validator("prop_name")`:** Runs immediately upon assignment in memory.
* **`@model_validator`:** Runs right before `.put()`, allowing you to safely compare multiple properties.

---

## 5. Queries & Aggregations

The query API syntax is highly compatible with NDB, including AST chaining with `==`, `>=`, `AND`, `OR`, `&`, and `|`. 

However, there are major enhancements:

### Native IN and NOT_IN
The new ODM supports `.IN()` and `.NOT_IN()` directly on the property and uses the related native operators of Firestore in Datastore mode instead of multiple OR conditions that ndb masked under the hood. 

### Server-Side Aggregations (Massive Upgrade)
In NDB, if you wanted to count entities, you had to loop over `keys_only` queries, or build complex sharded counters. 

The new ODM utilizes modern Datastore Server-Side Aggregations. You can instantly execute `Count`, `Sum`, and `Avg` entirely on Google's backend and also exposes the batch aggregate feature as well.

```python
# --- NEW ODM ---
from google_cloud_datastore_odm import Count, Sum

stats = Order.query().aggregate(
    total_orders=Count(),
    total_revenue=Sum(Order.price)
)
```

---

## 6. Transactions

The transaction API has been upgraded to support modern Python context managers and decorators.

* `ndb.transactional` ➡️ `@transactional(retries=5)`
* `ndb.transaction()` ➡️ `with transaction():`

### The "Read-Before-Write" Rule
The new ODM uses modern Firestore in Datastore mode, which relies on **Snapshot Isolation** and pure Optimistic Concurrency. 

In NDB, writes were buffered into the context cache. In the new ODM, **you must execute all your reads (`.get()`, `.query()`) before executing any writes (`.put()`) inside a transaction.** If you write to an entity, the transaction snapshot is considered "dirty" and further reads will raise an exception.

### No More Entity Group Limits
NDB forced you to use Ancestor Keys (Entity Groups) to run transactions, and limited you to 25 groups. Modern Datastore has **completely lifted this limit**. You can modify thousands of completely unrelated entities in a single transaction, bounded only by a 10 MiB total payload size. 

---

## 7. Lifecycle Hooks

NDB supported hooks like `_pre_put_hook`. The new ODM supports all of these, but with stricter Python signatures for read/delete operations.

Because a `.get()` or `.delete()` often happens *before* an instance exists in memory (e.g., `User.delete(key)`), **Read and Delete hooks must be defined as `@classmethod`s.**

```python
class TrackedModel(Model):
    
    # Write hooks are instance methods
    def _pre_put_hook(self):
        self.updated_at = datetime.now()

    # Read/Delete hooks MUST be class methods
    @classmethod
    def _pre_delete_hook(cls, key):
        print(f"About to delete {key}")
```
