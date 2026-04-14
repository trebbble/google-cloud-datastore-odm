"""
Query builder for the Google Cloud Datastore ODM.

This module is structured into three layers:
1. AST Nodes: Simple objects that represent filter/order logic.
2. Logic Functions: Global AND/OR helpers to group Nodes.
3. Query Engine: The main class that translates Nodes into Datastore SDK calls.
"""

from typing import TYPE_CHECKING, Any, Generator, List, Optional, Union

from google.cloud.datastore import query
from google.cloud.datastore.aggregation import CountAggregation

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
        from .properties import Property

        for arg in args:
            if isinstance(arg, OrderNode):
                self._orders.append(arg)
            elif isinstance(arg, Property):
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

        return _query

    def fetch(self, limit: Optional[int] = None) -> Generator["Model", None, None]:
        """Yields hydrated Model instances from the Datastore."""
        for entity in self._build().fetch(limit=limit):
            yield self.model_cls.from_entity(entity)

    def count(self) -> int:
        """Performs a server-side count aggregation (very fast)."""
        client = get_client(self.project, self.database)
        agg_query = client.aggregation_query(self._build())
        agg_query.add_aggregation(CountAggregation())

        results = list(agg_query.fetch())
        return results[0][0].value if results else 0
