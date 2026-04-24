# Google Cloud Datastore ODM

**A modern, fully-typed, Object Document Mapper for Google Cloud Datastore.**

Built for modern Python, this ODM bridges the gap between the raw `google-cloud-datastore` client and the developer-friendly ergonomics of the legacy App Engine NDB library. 

It features a declarative property system, intuitive AST-based query building, lightning-fast server-side aggregations, and intelligent ACID transactions with automatic concurrency retries.

---

## A Taste of the ODM

Stop wrestling with raw dictionaries. Define strict schemas and query them using pure, Pythonic syntax:

```python
from google_cloud_datastore_odm import Model, StringProperty, IntegerProperty, Sum

class Player(Model):
    name = StringProperty(required=True)
    team = StringProperty(choices=["red", "blue"])
    score = IntegerProperty(default=0)

# Create and save natively
player = Player(name="Alice", team="red", score=150)
player.put()

# Query using standard Python operators
top_red_players = Player.query().filter(Player.team == "red", Player.score > 100).fetch()

# Perform lightning-fast server-side aggregations
stats = Player.query().aggregate(total_score=Sum(Player.score))
print(f"Total points scored: {stats['total_score']}")
```

---

## Key Features

### 🏗️ Advanced Data Modeling
* **NDB Muscle Memory:** Familiar API including `.put()`, `.get()`, `.query()`, and `_pre_put` hooks.
* **Strict Validation:** Built-in type checking, property-level constraints (`required=True`, `choices`), and custom `@field_validator` and `@model_validator` decorators.
* **Complex Data Types:** Natively embed full models using `StructuredProperty`, or store dynamic data with `JsonProperty` and `PickleProperty`.
* **Cost Optimization:** Automatically bypass Datastore's 1500-byte index limits and compress massive text or binary payloads using `compressed=True`.

### 🔍 Powerful Querying
* **Pythonic AST Queries:** Chain filters using standard operators (`==`, `>=`, `!=`) and bitwise logic (`&`, `|`).
* **Server-Side Aggregations:** Delegate heavy math to Google's backend using `Count`, `Sum`, and `Avg`.
* **Cost-Effective Fetching:** Utilize `.projection()`, `.distinct_on()`, and `.keys_only()` to minimize read costs.
* **Cursor Pagination:** Easily build paginated APIs using native `.fetch_page()`.

### 🛡️ Enterprise Grade
* **Smart Transactions:** Execute ACID-compliant operations using the `with transaction():` context manager, or use the `@transactional(retries=5)` decorator to automatically handle optimistic concurrency collisions.
* **Multi-Tenancy & Routing:** Route data dynamically across different GCP Projects, Databases, and Namespaces using the `Meta` class or ad-hoc instance kwargs.
* **Zero-Overhead Batching:** Native support for `put_multi`, `get_multi`, and `delete_multi` to maximize network efficiency.

---

## Why this ODM?

The official `google-cloud-datastore` Python SDK is incredibly powerful, but it relies heavily on raw dictionaries (`Entity` objects). This leaves the burden of schema validation, type casting, and default-value assignment entirely up to the developer.

This ODM provides a robust, class-based structure that guarantees your data schema is respected *before* a single network request is made. If you try to save an invalid property, the ODM catches it in memory. If you try to run a query using an unindexed field, the ODM warns you before you waste a database read.

---

## Documentation Directory

Ready to dive in? Check out the guides below:

* 🚀 **[Getting Started](getting_started.md):** Installation and basic CRUD operations.
* 📚 **[Models & Properties](guide/models.md):** Aliasing, dictionaries, compression, and nested data.
* 🛡️ **[Validation & Hooks](guide/validation.md):** Strict data integrity and database lifecycle events.
* 🔎 **[Queries & Aggregations](guide/queries.md):** Complex filtering, pagination, and server-side math.
* 🔄 **[Transactions](guide/transactions.md):** ACID compliance and optimistic concurrency control.
* 🏢 **[Multi-Tenancy & Routing](guide/routing.md):** Isolating data across namespaces and databases.
