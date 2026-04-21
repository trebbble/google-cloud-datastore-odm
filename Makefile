.PHONY: setup test test-cov lint docs clean

setup:
	@echo "Syncing dependencies and installing in editable mode..."
	uv sync

test:
	uv run pytest

test-cov:
	uv run pytest --cov=google_cloud_datastore_odm --cov-report=term-missing --cov-report=xml

lint:
	uv run ruff check .

docs:
	uv run zensical serve

clean:
	rm -rf .pytest_cache .coverage coverage.xml site/
	find . -type d -name "__pycache__" -exec rm -r {} +
