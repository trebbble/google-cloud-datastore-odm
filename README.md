# Google Cloud Datastore ODM

[![CI](https://github.com/trebbble/google-cloud-datastore-odm/actions/workflows/ci.yml/badge.svg)](https://github.com/trebbble/google-cloud-datastore-odm/actions/workflows/ci.yml) ![Coverage](./coverage.svg)

### Documentation
https://trebbble.github.io/google-cloud-datastore-odm/

---

### Local Setup & Dependencies
The project uses [`uv`](https://github.com/astral-sh/uv) for lightning-fast dependency management.
```bash
# Install the package in editable mode along with all dev dependencies
uv sync
```

### Local emulators

```bash
# Start all emulators in the background
docker compose -f docker-compose.yml up -d --build

# Tear down and wipe data
docker compose -f docker-compose.yml down --volumes
```

- Environment variables to connect to emulators
  - Datastore dev emulator:
    ```bash
    DATASTORE_EMULATOR_HOST=localhost:10000
    GOOGLE_CLOUD_PROJECT=google-cloud-datastore-odm-dev
    ```

  - Datastore tests emulator:
    ```bash
    DATASTORE_EMULATOR_HOST=localhost:10001
    GOOGLE_CLOUD_PROJECT=google-cloud-datastore-odm-test
    ```

- Datastore emulator user interface at `localhost:10002`


### Testing & Linting


```bash
# Start all emulators in the background
docker compose -f docker-compose.yml up -d --build
# or start only datastore container dedicated for testing
docker compose -f docker-compose.yml up -d --build datastore-test

uv run pytest 
# Run tests with coverage and generate an XML report
uv run pytest --cov=google_cloud_datastore_odm --cov-report=xml --cov-report=term-missing
# Generate the local coverage badge
uv run genbadge coverage -i coverage.xml -o coverage.svg

# Run the linter & formatter
uv run ruff check
```


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
- [x] Transaction-bound queries
- [x] Aggregations
  - [x] Count
  - [x] Sum
  - [x] Avg
  - [x] Batch aggregate
- [x] Warnings for queries on unindexed properties (for normal filters or even projections)

### Persistence & Operations
- [x] Transactions
- [ ] Cache


### Schema & Metadata Introspection
- [x] Model schema introspection API
- [x] Field metadata exposure
- [x] Optional index declarations at the model level

### Async Support
- [ ] Async model API operations
- [ ] Async query API support
- [ ] Async transaction support
