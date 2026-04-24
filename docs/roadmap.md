# Project Roadmap

The Google Cloud Datastore ODM is actively developed. Below is the current status of features, migrating from the legacy App Engine NDB mindset to modern Python architecture.

---

## 🏗️ Core Model & Property System
- [x] Model base class
    - [x] Metaclass-driven configuration
      - [x] Model-level validation hooks
      - [x] Explicit model overrides via `Meta` class (`kind`, `namespace`, `project`, `database`)
- [x] Property system
    - [x] Descriptor-based field definitions
      - [x] Field defaults
      - [x] Field-level validation
      - [x] Properties:
        - [x] BooleanProperty
        - [x] IntegerProperty
        - [x] FloatProperty
        - [x] ~~BlobProperty~~ --> to be supported but renamed to `BytesProperty` 
        - [x] ~~CompressedTextProperty~~ --> support with `compressed` argument in properties that make sense
        - [x] TextProperty
        - [x] StringProperty
        - [x] GeoPtProperty
        - [x] PickleProperty
        - [x] JsonProperty
        - [x] ~~UserProperty~~ Deprecated, to be dropped.
        - [x] KeyProperty
        - [x] ~~BlobKeyProperty~~ Deprecated, to be dropped.
        - [x] DateTimeProperty
        - [x] DateProperty
        - [x] TimeProperty
        - [x] StructuredProperty
        - [x] ~~LocalStructuredProperty~~ To be dropped. StructuredProperty and JsonProperty can accomodate sufficiently.
        - [x] GenericProperty
        - [x] ComputedProperty
      - [ ] Polymodel Support (TBD)

---

## ⚙️ Model Core API
- [x] Datastore key expose and management
- [x] Key allocation helpers (`allocate_ids`, `allocate_key`)
- [x] Entity identity (`id` / `name`)
- [x] Entity hydration from raw datastore entities
- [x] Ancestor (hierarchical) key support
- [x] Dict-style and attribute-style access (`doc['field']` vs `doc.field`)
- [x] Basic CRUD operations (`put`, `get`, `delete`)
- [x] Bulk CRUD operations (`put_multi`, `get_multi`, `delete_multi`)
- [x] Lifecycle hooks (`_pre_put`, `_post_get`, etc.)
- [ ] Atomic `get_or_insert`

---

## 🔍 Query API
- [x] Pass-through queries with raw datastore fields and operators
- [x] ODM-style AST filtering:
    - [x] Operator overloading (`==`, `>`, `<=`, etc.)
      - [x] Logical grouping (`AND`, `OR`, `and_`, `or_`)
      - [x] Bitwise chaining (`&`, `|`)
      - [x] Native `IN` / `NOT_IN`
- [x] Limits
- [x] Ordered queries
- [x] Pagination with cursors (`fetch_page`)
- [x] Keys-only queries
- [x] Projection queries
- [x] Distinct queries
- [x] `.get()` queries for first or None
- [x] Transaction-bound queries
- [x] **Aggregations:**
    - [x] Server-side `Count`, `Sum`, and `Avg`
      - [x] Batch aggregate RPCs
- [x] Runtime warnings for queries or projections attempted on unindexed properties.

---

## 📄 Schema & Metadata Introspection
- [x] Schema & Metadata Introspection API
- [x] Field metadata exposure
- [x] Optional index declarations at the model level

---

## 💾 Persistence, Caching & Operations
- [x] Transactions
    - [x] Transaction context manager
    - [x] Transactional Decorator
- [ ] Cache support

---

## ⚡ Async Support

- [ ] Async model API operations (`put_async`, `get_async`)
- [ ] Async query API support (`fetch_async`)
- [ ] Async transaction support
