# Google Cloud Datastore ODM

[![CI](https://github.com/trebbble/google-cloud-datastore-odm/actions/workflows/ci.yml/badge.svg)](https://github.com/trebbble/google-cloud-datastore-odm/actions/workflows/ci.yml) ![Coverage](./coverage.svg)

### Documentation
https://trebbble.github.io/google-cloud-datastore-odm/

---

### Dependencies
- `uv sync all-groups`

### Local emulators
- `docker compose -f docker-compose.yml up -d --build`
- `docker compose -f docker-compose.yml down --volumes`

### Local usage
- Datastore emulator for dev:
    - `DATASTORE_EMULATOR_HOST=localhost:10000`
    - `GOOGLE_CLOUD_PROJECT=google-cloud-datastore-odm-dev`
- Datastore emulator for tests:
    - `DATASTORE_EMULATOR_HOST=localhost:10001`
    - `GOOGLE_CLOUD_PROJECT=google-cloud-datastore-odm-test`
- Datastore emulator UI : `localhost:10002`


### Local tests & Coverage:
  - From root folder `docker compose -f docker-compose.yml up -d --build datastore-test`
  - `uv run pytest` or `python3.14 -m pytest` 
  - To run with coverage and generate an XML report: `uv run pytest --cov=src --cov-report=xml --cov-report=term-missing`
  - To generate the local coverage badge (requires the XML report): `uv run genbadge coverage -i coverage.xml -o coverage.svg`
- Run linter `uv run ruff check`


### Local docs:
- `uv run zensical serve`
- Visit at http://localhost:8000

## Roadmap

### Core Model & Property System
- [x] Model base class
  - [x] Metaclass-driven configuration
  - [x] Model-level validation hooks
  - [x] Explicit model overrides via `Meta` class
    - [x] `kind`
    - [x] `namespace`
    - [x] `project`
    - [x] `database`
- [x] Property system
  - [x] Descriptor-based field definitions
  - [x] Field defaults
  - [x] Field-level validation
  - Properties:
    - [x] BooleanProperty
    - [x] IntegerProperty
    - [x] FloatProperty
    - [x] ~~BlobProperty~~ --> to be supported but renamed to `BytesProperty` 
    - [x] ~~CompressedTextProperty~~ --> support with `compressed` argument in properties that make sense:
       - TextProperty
       - JsonProperty
    - [x] TextProperty
    - [x] StringProperty
    - [ ] GeoPtProperty
    - [ ] PickleProperty
    - [x] JsonProperty
    - [x] ~~UserProperty~~ Deprecated, to be dropped.
    - [x] KeyProperty
    - [x] ~~BlobKeyProperty~~ Deprecated, to be dropped.
    - [x] DateTimeProperty
    - [x] DateProperty
    - [x] TimeProperty
    - [ ] StructuredProperty
    - [x] ~~LocalStructuredProperty~~ To be dropped. If structured and indexed is needed one can use StructuredProperty. If structured but not indexexed is needed, then they can use JsonProperty
    - [ ] GenericProperty
    - [ ] ComputedProperty
  - [ ] Polymodel Support
- [x] Model core API
  - [x] Datastore key expose and management
  - [x] Key allocation helpers
  - [x] Entity identity (`id` / `name`)
  - [x] Entity hydration from datastore
  - [x] Ancestor (hierarchical) key support
  - [x] Dict-style and attribute-style access
  - [x] Basic CRUD operations
  - [x] Bulk CRUD operations
  - [x] Lifecycle hooks
  - [ ] Atomic get_or_insert

### Query API
- [x] Pass through queries with raw datastore fields and operators
- [x] ODM style filtering
  - [x] AST and chained filters
  - [x] Equality/Unequality
  - [x] Logical and/or
  - [x] Native IN/NOT_IN
- [x] Limits
- [x] Pagination with cursors
- [x] Ordered queries
- [x] Keys-only queries
- [x] Projection queries
- [x] Distinct queries
- [x] .get() queries for first or None
- [ ] Transaction-bound queries
- [x] Aggregations
  - [x] Count
  - [x] Sum
  - [x] Avg
  - [x] Batch aggregate
- [ ] Warnings for queries on unindexed properties (for normal filters or even projections)

### Persistence & Operations
- [ ] Transactions
- [ ] Cache


### Schema & Metadata Introspection
- [x] Model schema introspection API
- [x] Field metadata exposure
- [x] Optional index declarations at the model level
- [ ] Index introspection (where possible)

### Async Support
- [ ] Async model API operations
- [ ] Async query API support
- [ ] Async transaction support
