"""
Query builder for the Google Cloud Datastore ODM.

This module is structured into three layers:
1. AST Nodes: Simple objects that represent filter/order logic.
2. Logic Functions: Global AND/OR helpers to group Nodes.
3. Query Engine: The main class that translates Nodes into Datastore SDK calls.
"""

from typing import TYPE_CHECKING, Any, Dict, Generator, List, Optional, Union

from google.cloud.datastore import query
from google.cloud.datastore.aggregation import AvgAggregation as Avg
from google.cloud.datastore.aggregation import CountAggregation as Count
from google.cloud.datastore.aggregation import SumAggregation as Sum

from .client import get_client

if TYPE_CHECKING:
    from .model import Model
    from .properties import Property


class Node:
    """Base query node. Supports bitwise style: (Prop == x) & (Prop == y)."""
    def __and__(self, other: "Node") -> "CompositeNode":
        return and_(self, other)

    def __or__(self, other: "Node") -> "CompositeNode":
        return or_(self, other)


class FilterNode(Node):
    """Stores the name, operator, and value of a single filter."""
    def __init__(self, name: str, op: str, value: Any):
        self.name, self.op, self.value = name, op, value


class CompositeNode(Node):
    """Stores a collection of nodes joined by logical and/or operators."""
    def __init__(self, op: str, filters: List[Node]):
        self.op, self.filters = op, filters


class OrderNode:
    """Stores sort direction for a property."""
    def __init__(self, name: str, descending: bool):
        self.name, self.descending = name, descending


def and_(*filters: Node) -> CompositeNode:
    """Combines filters with AND logic."""
    return CompositeNode("AND", list(filters))


def or_(*filters: Node) -> CompositeNode:
    """Combines filters with OR logic."""
    return CompositeNode("OR", list(filters))


AND, OR = and_, or_


class Query:
    def __init__(
            self,
            model_cls: "type[Model]",
            project: Optional[str] = None,
            database: Optional[str] = None,
            namespace: Optional[str] = None,
    ):
        self.model_cls = model_cls
        self.project, self.database, self.namespace = project, database, namespace
        self._filters: List[Node] = []
        self._orders: List[OrderNode] = []
        self._projection: List[Union[str, "Property"]] = []
        self._distinct_on: List[Union[str, "Property"]] = []
        self._keys_only: bool = False

    def projection(self, *args: Union[str, "Property"]) -> "Query":
        """Sets the projection fields for the query."""
        self._projection.extend(args)
        return self

    def distinct_on(self, *args: Union[str, "Property"]) -> "Query":
        """Sets the distinct_on fields for the query."""
        self._distinct_on.extend(args)
        return self

    def keys_only(self) -> "Query":
        """Marks the query to return only Datastore Keys."""
        self._keys_only = True
        return self

    def filter(self, *args: Union[Node, str]) -> "Query":
        """Adds filters to the query. Supports both Node objects and raw strings."""
        if len(args) == 3 and all(isinstance(a, str) for a in args[:2]):
            self._filters.append(FilterNode(args[0], args[1], args[2]))
        else:
            for arg in args:
                if isinstance(arg, Node):
                    self._filters.append(arg)
                else:
                    raise ValueError(f"Invalid filter: {arg}. Use Model.prop == val.")
        return self

    def order(self, *args: Union[OrderNode, str, "Property"]) -> "Query":
        """Adds ordering. Accepts -Prop, Prop, or raw strings."""

        for arg in args:
            if isinstance(arg, OrderNode):
                self._orders.append(arg)
            elif hasattr(arg, 'datastore_name'):
                self._orders.append(OrderNode(arg.datastore_name, False))
            elif isinstance(arg, str):
                is_desc = arg.startswith("-")
                self._orders.append(OrderNode(arg[1:] if is_desc else arg, is_desc))
        return self

    def _translate(self, node: Node) -> Union[query.PropertyFilter, query.And, query.Or]:
        """Recursive translation from ODM Nodes to SDK Query objects."""
        if isinstance(node, FilterNode):
            return query.PropertyFilter(node.name, node.op, node.value)

        if isinstance(node, CompositeNode):
            sdk_filters = [self._translate(f) for f in node.filters]
            return query.And(sdk_filters) if node.op == "AND" else query.Or(sdk_filters)

        raise TypeError(f"Unknown node type: {type(node)}")

    def _build(self) -> query.Query:
        """Helper to prepare the native SDK Query object."""
        client = get_client(self.project, self.database)
        _query = client.query(kind=self.model_cls.kind(), namespace=self.namespace)

        for node in self._filters:
            _query.add_filter(filter=self._translate(node))

        if self._orders:
            _query.order = [f"{'-' if o.descending else ''}{o.name}" for o in self._orders]

        if self._projection:
            mapped_proj = [getattr(p, 'datastore_name', p) for p in self._projection]
            _query.projection = mapped_proj

        if self._distinct_on:
            mapped_distinct = [getattr(d, 'datastore_name', d) for d in self._distinct_on]
            _query.distinct_on = mapped_distinct

        if self._keys_only:
            _query.keys_only()

        return _query

    def _hydrate_entity(
            self,
            entity: Any,
            keys_only: bool,
            is_projected: bool
    ) -> Union["Model", Any]:
        """Shared logic to convert a raw Datastore entity into a Key or a Model."""
        if keys_only:
            return entity.key
        return self.model_cls.from_entity(entity, _is_projected=is_projected)

    def fetch(self, limit: Optional[int] = None) -> Generator[Union["Model", Any], None, None]:
        """Yields hydrated Model instances (or Keys) from the Datastore."""
        native_query = self._build()

        is_projected = bool(self._projection)

        for entity in native_query.fetch(limit=limit):
            yield self._hydrate_entity(entity=entity, keys_only=self._keys_only, is_projected=is_projected)

    def fetch_page(
            self,
            page_size: int,
            start_cursor: Optional[bytes] = None
    ) -> tuple[List[Union["Model", Any]], Optional[bytes], bool]:
        """
        Fetches a specific page of results, returning metadata needed for pagination.

        Returns:
            Tuple containing:
            - A list of hydrated Model instances (or Keys)
            - The cursor bytes to fetch the next page (or None)
            - A boolean indicating if there are more results
        """
        native_query = self._build()
        is_projected = bool(self._projection)

        query_iter = native_query.fetch(limit=page_size, start_cursor=start_cursor)

        try:
            page = next(query_iter.pages)
            raw_entities = list(page)
        except StopIteration:
            return [], None, False

        results = [
            self._hydrate_entity(entity=raw_entity, keys_only=self._keys_only, is_projected=is_projected)
            for raw_entity in raw_entities
        ]

        next_cursor = query_iter.next_page_token
        has_more = bool(next_cursor) and len(results) == page_size

        return results, next_cursor if has_more else None, has_more

    def get(self) -> Optional["Model"]:
        """
        Executes the query and returns the first matching Model instance,
        or None if no results are found.
        """
        results = list(self.fetch(limit=1))
        return results[0] if results else None

    def count(self) -> int:
        """Performs a server-side count aggregation (very fast)."""
        client = get_client(self.project, self.database)
        agg_query = client.aggregation_query(self._build())
        agg_query.add_aggregation(Count())

        results = list(agg_query.fetch())
        return results[0][0].value if results else 0

    def sum(self, property_field: Union[str, "Property"]) -> Union[int, float]:
        """Performs a fast server-side sum aggregation on a specific property."""
        prop_name = getattr(property_field, 'datastore_name', property_field)

        client = get_client(self.project, self.database)
        agg_query = client.aggregation_query(self._build())
        agg_query.add_aggregation(Sum(prop_name))

        results = list(agg_query.fetch())
        return results[0][0].value if results and results[0] else 0

    def avg(self, property_field: Union[str, "Property"]) -> float:
        """Performs a fast server-side average aggregation on a specific property."""
        prop_name = getattr(property_field, 'datastore_name', property_field)

        client = get_client(self.project, self.database)
        agg_query = client.aggregation_query(self._build())
        agg_query.add_aggregation(Avg(prop_name))

        results = list(agg_query.fetch())

        return results[0][0].value if results and results[0] else None

    def aggregate(self, **kwargs: Union[Count, Sum, Avg]) -> Dict[str, Any]:
        """
        Performs multiple aggregations in a single Datastore RPC call.

        Args:
            **kwargs: Alias names mapped to Aggregation objects (Count, Sum, or Avg).

        Returns:
            Dict[str, Any]: A dictionary mapping your aliases to their aggregated values.
        """
        client = get_client(self.project, self.database)
        agg_query = client.aggregation_query(self._build())

        for alias, agg_obj in kwargs.items():
            if not isinstance(agg_obj, (Count, Sum, Avg)):
                raise TypeError(
                    f"Aggregation '{alias}' must be a Count, Sum, or Avg object. "
                    f"Got {type(agg_obj).__name__} instead."
                )

            if isinstance(agg_obj, (Sum, Avg)):
                if hasattr(agg_obj.property_ref, 'datastore_name'):
                    agg_obj.property_ref = agg_obj.property_ref.datastore_name

            agg_obj.alias = alias
            agg_query.add_aggregation(agg_obj)

        results = list(agg_query.fetch())

        if not results or not results[0]:
            return {
                alias: None
                for alias in kwargs
            }

        result_map = {
            res.alias: res.value
            for res in results[0]
        }

        return {
            alias: result_map.get(alias)
            for alias in kwargs
        }
