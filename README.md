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


### Local tests:
  - From root folder `docker compose -f docker-compose.yml up -d --build` datastore-test
  - `uv run pytest` or `python3.12 -m pytest` 
- Run linter `uv run ruff check`


## Roadmap

### Core Model & Field System
- [ ] Model base class
  - [ ] Metaclass-driven configuration
  - [ ] Model-level validation hooks
  - [ ] Explicit model overrides via `Meta` class
    - [ ] `kind`
    - [ ] `namespace`
    - [ ] `project`
- [ ] Field system
  - [ ] Descriptor-based field definitions
  - [ ] Field defaults
  - [ ] Field-level validation
- [ ] Datastore key handling
  - [ ] Key allocation helpers
  - [ ] Entity identity (`id` / `name`)
  - [ ] Entity hydration from datastore
  - [ ] Ancestor (hierarchical) key support
- [ ] Dict-style and attribute-style access

### Query System
- [ ] Query API
  - [ ] Basic filtering
  - [ ] Limits
  - [ ] Fetching / iteration
- [ ] Chained query filters
- [ ] Transaction-bound queries
- [ ] Warnings for potentially unindexed queries

### Persistence & Operations
- [ ] Bulk operations
  - [ ] `put_multi`
  - [ ] `delete_multi`
- [ ] Lightweight transaction context manager

### Schema & Metadata Introspection
- [ ] Model schema introspection API
- [ ] Field metadata exposure
- [ ] Optional index declarations at the model level
- [ ] Index introspection (where possible)

### Async Support
- [ ] Async model operations
- [ ] Async query support
- [ ] Async transaction support
