# Google Cloud Datastore ODM

**A modern, fully-typed, Object Document Mapper for Google Cloud Datastore.**

Built for modern Python, this ODM bridges the gap between the raw `google-cloud-datastore` client and the developer-friendly ergonomics of the legacy App Engine NDB library.

It features a declarative property system, intuitive AST-based query building, and intelligent, context-aware ACID transactions with automatic concurrency retries.

## Key Features

* **NDB Muscle Memory:** Familiar API including `.put()`, `.get()`, `.query()`, `_pre_put` hooks etc.
* **Modern Python:** Fully type-hinted and strictly validated.
* **Zero-Overhead Batching:** Native support for `put_multi`, `get_multi`, and `delete_multi`.
* **Descriptor-based Properties:** Elegant schema definitions using `StringProperty`, `IntegerProperty`, etc.
* **Smart Aliasing:** Seamlessly map Python attributes to legacy Datastore column names.
* **Built-in Validation:** Extensive property-level and model-level validation decorators.

## Why this ODM?
The official `google-cloud-datastore` library relies heavily on raw dictionaries (`Entity` objects). This ODM provides a robust class-based structure that guarantees your data schema is respected before a single network request is made.
