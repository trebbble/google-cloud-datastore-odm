"""
Query builder for the Google Cloud Datastore ODM.

This module provides the `Query` class, which offers a fluent, chainable API
for constructing and executing Datastore queries. It automatically handles
the translation of raw Datastore entities back into fully hydrated Python models.
"""

from typing import TYPE_CHECKING, Any, Generator, Optional

from google.cloud.datastore.query import PropertyFilter

from .client import get_client

if TYPE_CHECKING:
    from .model import Model


class Query:
    """
    A fluent query builder for Datastore entities.

    This class wraps the native `google.cloud.datastore.Query` object, providing
    a chainable interface for adding filters. When executed via `fetch()`,
    it automatically hydrates the raw Datastore entities back into your ODM `Model` instances.
    """

    def __init__(
            self,
            model_cls: "type[Model]",
            project: Optional[str] = None,
            database: Optional[str] = None,
            namespace: Optional[str] = None,
    ):
        """
        Initialize a new Query for a specific model kind.

        Args:
            model_cls (type[Model]): The Model class this query will return instances of.
                The query automatically targets the kind associated with this class.
            project (Optional[str]): An optional project override.
            database (Optional[str]): An optional database override.
            namespace (Optional[str]): An optional namespace override.
        """
        self.model_cls = model_cls
        self.project = project
        self.database = database
        self.namespace = namespace
        self._filters: list[tuple[str, str, Any]] = []

    def filter(self, field: str, op: str, value: Any) -> "Query":
        """Add a property filter to the query.

        Filters can be chained together. Currently, this method requires the actual
        Datastore property name (e.g., if a Python property is aliased using `name="..."`,
        you must query using the aliased name).

        Args:
            field (str): The Datastore property name to filter on.
            op (str): The comparison operator (e.g., '=', '<', '<=', '>', '>=', 'IN').
            value (Any): The value to compare against.

        Returns:
            Query: The current Query instance to allow method chaining.

        Example:
            ```python
            # Chain multiple filters together
            query = (
                Article.query()
                .filter("author_name", "=", "Alice")
                .filter("status", "=", "published")
            )
            ```
        """
        self._filters.append((field, op, value))
        return self

    def fetch(self, limit: Optional[int] = None) -> Generator["Model", None, None]:
        """Execute the query and yield hydrated model instances.

        This method acts as a generator, yielding instances one by one as they are
        retrieved from the Datastore. This is memory-efficient for large datasets.

        Args:
            limit (Optional[int]): The maximum number of entities to return.
                Defaults to None (fetch all matching entities).

        Yields:
            Model: A fully hydrated instance of the target model class.

        Example:
            ```python
            # Fetch the first 10 published articles
            query = Article.query().filter("status", "=", "published")

            for article in query.fetch(limit=10):
                print(article.title)
            ```
        """
        client = get_client(project=self.project, database=self.database)
        kwargs = {}

        if self.namespace:
            kwargs["namespace"] = self.namespace

        query = client.query(kind=self.model_cls.kind(), **kwargs)

        for name, op, value in self._filters:
            query.add_filter(filter=PropertyFilter(name, op, value))

        for entity in query.fetch(limit=limit):
            yield self.model_cls.from_entity(entity)
