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
  - [ ] Explicit model overrides via `Meta` class
    - [ ] `kind`
    - [ ] `namespace`
    - [ ] `project`
- [x] Property system
  - [x] Descriptor-based field definitions
  - [x] Field defaults
  - [x] Field-level validation
  - Properties:
    - [x] BooleanProperty
    - [x] IntegerProperty
    - [x] FloatProperty
    - [ ] BlobProperty
    - [ ] CompressedTextProperty
    - [x] TextProperty
    - [x] StringProperty
    - [ ] GeoPtProperty
    - [ ] PickleProperty
    - [x] JsonProperty
    - [ ] UserProperty
    - [ ] KeyProperty
    - [ ] BlobKeyProperty
    - [x] DateTimeProperty
    - [x] DateProperty
    - [x] TimeProperty
    - [ ] StructuredProperty
    - [ ] LocalStructuredProperty
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
- [x] Pass through queries
- [ ] ODM style filtering
- [ ] Limits
- [ ] Pagination / Cursors
- [ ] Keys-only queries
- [ ] Projection queries
- [ ] Chained query filters
- [ ] Transaction-bound queries
- [ ] Aggregate queries
- [ ] Warnings for potentially unindexed queries

### Persistence & Operations
- [ ] Context
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
