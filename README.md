# Google Cloud Datastore ODM
[![CI](https://github.com/trebbble/google-cloud-datastore-odm/actions/workflows/ci.yml/badge.svg)](https://github.com/trebbble/google-cloud-datastore-odm/actions/workflows/ci.yml) ![Coverage](./coverage.svg)

Google Cloud Datastore ODM is a modern, fully-typed Python library that brings the beloved developer experience of App Engine's NDB to the modern Datastore SDK. Built for Python 3.10+, it bridges the gap between raw API calls and enterprise-grade application development. It features a declarative property system, intuitive AST-based query building, and intelligent, context-aware ACID transactions with automatic concurrency retries.

### Documentation
https://trebbble.github.io/google-cloud-datastore-odm/

---

### Local Setup & Dependencies
The project uses [`uv`](https://github.com/astral-sh/uv) for lightning-fast dependency management.
```bash
# Install the package in editable mode along with all dev dependencies
uv sync
# or use makefile commands
make setup
```

### Local emulators

```bash
# Start all emulators in the background
docker compose -f docker-compose.yml up -d --build

# Tear down and wipe data
docker compose -f docker-compose.yml down --volumes
```

- Environment variables to connect to emulators
  - Datastore dev emulator - make sure to set them up in case of local dev; see .env.example:
    ```bash
    DATASTORE_EMULATOR_HOST=localhost:10000
    GOOGLE_CLOUD_PROJECT=google-cloud-datastore-odm-dev
    ```

  - Datastore tests emulator - hardcoded already in test suite:
    ```bash
    DATASTORE_EMULATOR_HOST=localhost:10001
    GOOGLE_CLOUD_PROJECT=google-cloud-datastore-odm-test
    ```

- Datastore emulator user interface at `localhost:10002`


### Running examples, testing & linting

```bash
# Start all emulators in the background
docker compose -f docker-compose.yml up -d --build
# or start only datastore container dedicated for testing
docker compose -f docker-compose.yml up -d --build datastore-test

# run examples from examples folder
uv run python examples/01_properties.py

# run tests with uv
uv run pytest 
# or use makefile commands
make test

# Run tests with coverage and generate an XML report
uv run pytest --cov=google_cloud_datastore_odm --cov-report=xml --cov-report=term-missing
# or use makefile commands
make test-cov

# Run the linter & formatter
uv run ruff check
# or use makefile commands
make lint
# for autofixes
uv run ruff check --fix
```

### Local docs:
- `uv run zensical serve`
- Visit at http://localhost:8000
