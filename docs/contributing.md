# Contributing to Google Cloud Datastore ODM

First off, thank you for considering contributing to the Google Cloud Datastore ODM! It's people like you that make open-source software such a great community.

## 🐛 Found a Bug or Have a Feature Request?
If you find a bug or have an idea for a new feature, please open an issue on GitHub.
* **For bugs:** Please include a minimal, reproducible code example and the version of the library you are using.
* **For features:** Please explain the use case and how it benefits the broader community.

## 💻 Local Development Setup

We use [`uv`](https://github.com/astral-sh/uv) for lightning-fast dependency management and Docker to run local Datastore emulators.

### 1. Prerequisites
* Python 3.10+
* Docker
* uv

### 2. Installation
Clone the repository and setup.
```bash
git clone https://github.com/trebbble/google-cloud-datastore-odm.git
cd google-cloud-datastore-odm

# Install the package in editable mode along with all dev dependencies
uv sync
# or use makefile commands
make setup
```


### 3. Start the Emulators
You must run the local emulators to execute the test suite, run examples, or develop locally.
```bash
# Start all emulators in the background
docker compose -f docker-compose.yml up -d --build
# or start only datastore container dedicated for testing
docker compose -f docker-compose.yml up -d --build datastore-test
```

- Environment variables to connect to emulators
  - Datastore dev emulator - make sure to set them up in case of local dev; see `.env.example`:
    ```bash
    DATASTORE_EMULATOR_HOST=localhost:10000
    GOOGLE_CLOUD_PROJECT=google-cloud-datastore-odm-dev
    ```

  - Datastore tests emulator - hardcoded already in test suite:
    ```bash
    DATASTORE_EMULATOR_HOST=localhost:10001
    GOOGLE_CLOUD_PROJECT=google-cloud-datastore-odm-test
    ```

- Access Datastore emulator user interface at `localhost:10002`

### 🛠️ Development Workflow
We provide a `Makefile` to simplify common development tasks. 
Run these from the root directory of the cloned repository.

* **Setup:** Create a virtual environment and install the package in editable mode: `make setup`
* **Test:** Run tests: `make test`
* **Coverage:** Run tests with coverage: `make test-cov`
* **Linting:** Run the linter: `make lint`
* **Docs:** Serve local documentation: `make docs`
* **Cleanup:** Remove cache and temporary files: `make clean`
* **Examples** Run examples from related folder: `uv run python examples/01_properties.py`  

## 🚀 Submitting a Pull Request
* **Fork** the repository and create your branch from `main`.
* **Branch Naming:** Use a descriptive prefix (e.g., `feat/add-pagination`, `fix/query-bug`, `docs/update-readme`). 
* **Commit Messages:** Try to use [Conventional Commits](https://www.conventionalcommits.org/en/v1.0.0/) (e.g., `feat: added async support`, `fix: resolved key allocation bug`).
* **Test Coverage:** All new features must include tests. We strive to maintain 100% test coverage.
* **Type Hinting:** We strictly enforce Python type hints across the public API.
* **Test Locally:** Run `make test-cov` and `make lint` to ensure your changes pass all local checks. 
* **Open a PR:** Describe your changes in detail, link to any relevant issues, and submit! Our GitHub Actions CI will run the test suite against multiple Python versions.


## 💾 Commands cheatsheet

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

# local docs
make docs
# or 
uv run zensical serve
# Access at http://localhost:8000

# cache and temp files cleanup
make clean
```

### Thank you for contributing!
