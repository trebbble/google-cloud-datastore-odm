from typing import TYPE_CHECKING, Any, Generator, Optional
from .client import get_client
from google.cloud.datastore.query import PropertyFilter

if TYPE_CHECKING:
    from .model import Model  # Only for static analysis


class Query:
    """Query builder for Datastore."""

    def __init__(self, model_cls: "type[Model]"):
        self.model_cls = model_cls
        self._filters: list[tuple[str, str, Any]] = []

    def filter(self, field: str, op: str, value: Any) -> "Query":
        self._filters.append((field, op, value))
        return self

    def fetch(self, limit: Optional[int] = None) -> Generator["Model", None, None]:
        client = get_client()
        query = client.query(kind=self.model_cls.kind())

        for name, op, value in self._filters:
            query.add_filter(filter=PropertyFilter(name, op, value))

        for entity in query.fetch(limit=limit):
            yield self.model_cls.from_entity(entity)
