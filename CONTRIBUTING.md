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
Clone the repository.

    git clone https://github.com/trebbble/google-cloud-datastore-odm.git
    cd google-cloud-datastore-odm

### 3. Start the Emulators
You must run the local emulators to execute the test suite, run examples, or develop locally.

    docker compose -f docker-compose.yml up -d --build

### 🛠️ Development Workflow
We provide a `Makefile` to simplify common development tasks. You do not need to manually activate the virtual environment if you use these commands. 
Run these from the root directory of the cloned repository.

* **Setup:** Create a virtual environment and install the package in editable mode: `make setup`
* **Test:** Run tests: `make test`
* **Coverage:** Run tests with coverage: `make test-cov`
* **Linting:** Run the linter: `make lint`
* **Docs:** Serve local documentation: `make docs`
* **Cleanup:** Remove cache and temporary files: `make clean`

## 🚀 Submitting a Pull Request
* **Fork** the repository and create your branch from `main`.
* **Branch Naming:** Use a descriptive prefix (e.g., `feat/add-pagination`, `fix/query-bug`, `docs/update-readme`). 
* **Commit Messages:** Try to use [Conventional Commits](https://www.conventionalcommits.org/en/v1.0.0/) (e.g., `feat: added async support`, `fix: resolved key allocation bug`).
* **Test Coverage:** All new features must include tests. We strive to maintain 100% test coverage.
* **Type Hinting:** We strictly enforce Python type hints across the public API.
* **Test Locally:** Run `make test-cov` and `make lint` to ensure your changes pass all local checks. 
* **Open a PR:** Describe your changes in detail, link to any relevant issues, and submit! Our GitHub Actions CI will run the test suite against multiple Python versions.

Thank you for contributing!
