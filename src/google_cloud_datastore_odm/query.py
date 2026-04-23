"""
Query builder for the Google Cloud Datastore ODM.

This module is structured into three layers:
    - AST Nodes: Simple objects that represent filter/order logic.
    - Logic Functions: Global AND/OR helpers to group Nodes.
    - Query Engine: The main class that translates Nodes into Datastore SDK calls.
"""

import inspect
import os
import warnings
from collections.abc import Generator
from typing import TYPE_CHECKING, Any

from google.cloud.datastore import query
from google.cloud.datastore.aggregation import AvgAggregation as Avg
from google.cloud.datastore.aggregation import CountAggregation as Count
from google.cloud.datastore.aggregation import SumAggregation as Sum

from .client import get_client

if TYPE_CHECKING:
    from google.cloud import datastore

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
        self.name = name
        self.op = op
        self.value = value


class CompositeNode(Node):
    """Stores a collection of nodes joined by logical and/or operators."""

    def __init__(self, op: str, filters: list[Node]):
        self.op = op
        self.filters = filters


class OrderNode:
    """Stores sort direction for a property."""

    def __init__(self, name: str, descending: bool):
        self.name = name
        self.descending = descending


def and_(*filters: Node) -> CompositeNode:
    """Combines multiple filters with AND logic.

    Args:
        *filters (Node): Two or more filter nodes.

    Returns:
        CompositeNode: A logical AND grouping of the filters.

    Examples:
        ```python
        q = User.query().filter(and_(User.age >= 18, User.status == "active"))
        ```
    """
    return CompositeNode("AND", list(filters))


def or_(*filters: Node) -> CompositeNode:
    """Combines multiple filters with OR logic.

    Args:
        *filters (Node): Two or more filter nodes.

    Returns:
        CompositeNode: A logical OR grouping of the filters.

    Examples:
        ```python
        q = User.query().filter(or_(User.role == "admin", User.role == "editor"))
        ```
    """
    return CompositeNode("OR", list(filters))


# Aliases for developers transitioning from App Engine NDB
AND = and_
OR = or_


class Query:
    """The main Query builder for fetching entities from Google Cloud Datastore.

    This class provides a fluent, chainable API for building complex Datastore
    queries using Python-native property comparisons.
    """

    def __init__(
            self,
            model_cls: "type[Model]",
            project: str | None = None,
            database: str | None = None,
            namespace: str | None = None,
    ):
        self.model_cls = model_cls
        self.project = project
        self.database = database
        self.namespace = namespace

        self._filters: list[Node] = []
        self._orders: list[OrderNode] = []
        self._projection: "list[str | Property]" = []
        self._distinct_on: "list[str | Property]" = []
        self._keys_only: bool = False

    def projection(self, *args: "str | Property") -> "Query":
        """Sets the projection fields for the query.

        Projection queries are significantly faster and cheaper because they
        only retrieve specific fields from the Datastore rather than the entire entity.

        Args:
            *args (str | Property): The properties to retrieve.

        Returns:
            Query: The chainable query instance.

        Examples:
            ```python
            # Fetch only the email addresses of all users
            users = User.query().projection(User.email).fetch()
            ```
        """
        self._projection.extend(args)
        return self

    def distinct_on(self, *args: "str | Property") -> "Query":
        """Sets the fields to use for grouping distinct results.

        Args:
            *args (str | Property): The properties to group by.

        Returns:
            Query: The chainable query instance.

        Examples:
            ```python
            # Find all unique countries users are from
            unique_countries = User.query().distinct_on(User.country).fetch()
            ```
        """
        self._distinct_on.extend(args)
        return self

    def keys_only(self) -> "Query":
        """Marks the query to return only Datastore Keys instead of full entities.

        Keys-only queries are incredibly fast and cost-effective. Use them when
        you only need to check for existence or perform batch deletions.

        Returns:
            Query: The chainable query instance.
        """
        self._keys_only = True
        return self

    def filter(self, *args: "Node | str") -> "Query":
        """Adds filters to the query.

        Supports both standard ODM `Property` comparisons (recommended) and
        raw string passthrough for edge cases.

        Args:
            *args (Node | str): Filter nodes generated by comparing properties,
                or three raw strings (name, operator, value) for passthrough.

        Returns:
            Query: The chainable query instance.

        Raises:
            ValueError: If the arguments are malformed.

        Examples:
            ```python
            # Standard Property comparison
            q = User.query().filter(User.age >= 18)

            # Multiple implicit AND filters
            q = User.query().filter(User.age >= 18, User.is_active == True)

            # Composite Logic
            q = User.query().filter(OR(User.role == "admin", User.score > 100))
            ```
        """
        if len(args) == 3 and all(isinstance(a, str) for a in args[:2]):
            self._filters.append(FilterNode(args[0], args[1], args[2]))
        else:
            for arg in args:
                if isinstance(arg, Node):
                    self._filters.append(arg)
                else:
                    raise ValueError(f"Invalid filter: {arg}. Use Model.prop == val.")
        return self

    def order(self, *args: "OrderNode | str | Property") -> "Query":
        """Adds ordering/sorting to the query.

        Supports unary operators (`-` for descending, `+` for ascending) directly
        on properties, or raw string field names.

        Args:
            *args (OrderNode | str | Property): The properties to sort by.

        Returns:
            Query: The chainable query instance.

        Examples:
            ```python
            # Sort by highest score first, then alphabetically by name
            q = User.query().order(-User.score, User.name)
            ```
        """
        for arg in args:
            if isinstance(arg, OrderNode):
                self._orders.append(arg)
            elif hasattr(arg, 'datastore_name'):
                self._orders.append(OrderNode(arg.datastore_name, False))
            elif isinstance(arg, str):
                is_desc = arg.startswith("-")
                self._orders.append(OrderNode(arg[1:] if is_desc else arg, is_desc))
        return self

    def _warn_for_unindexed_properties(self) -> None:
        """Scans the translated query state and warns if unindexed properties are used."""
        # noinspection PyProtectedMember
        model_properties = self.model_cls._properties
        if not model_properties:
            return

        used_datastore_names = set()

        def extract_filter_names(node: Node) -> None:
            if isinstance(node, FilterNode):
                used_datastore_names.add(node.name)
            elif isinstance(node, CompositeNode):
                for f in node.filters:
                    extract_filter_names(f)

        for f_node in self._filters:
            extract_filter_names(f_node)

        for o_node in self._orders:
            used_datastore_names.add(o_node.name)

        for p in self._projection + self._distinct_on:
            if hasattr(p, 'datastore_name'):
                used_datastore_names.add(p.datastore_name)
            elif isinstance(p, str):
                used_datastore_names.add(p)

        unindexed_found = []
        for prop in model_properties.values():
            if prop.datastore_name in used_datastore_names and not prop.indexed:
                # noinspection PyProtectedMember
                unindexed_found.append(prop._python_name)

        if unindexed_found:
            dynamic_stacklevel = 1
            try:
                frame = inspect.currentframe()
                odm_dir = os.path.dirname(__file__)

                while frame:
                    if odm_dir not in frame.f_code.co_filename:
                        break
                    dynamic_stacklevel += 1
                    frame = frame.f_back
            except Exception:  # noqa
                dynamic_stacklevel = 5

            warnings.warn(
                f"This query relies on unindexed properties of model "
                f"'{self.model_cls.kind()}': {unindexed_found}. "
                f"Datastore does not maintain indexes for these fields. "
                f"This will likely result in zero results or an empty projection.",
                UserWarning,
                stacklevel=dynamic_stacklevel
            )

    def _translate(self, node: Node) -> query.PropertyFilter | query.And | query.Or:
        """Recursive translation from ODM Nodes to SDK Query objects."""
        if isinstance(node, FilterNode):
            return query.PropertyFilter(node.name, node.op, node.value)

        if isinstance(node, CompositeNode):
            sdk_filters = [self._translate(f) for f in node.filters]
            return query.And(sdk_filters) if node.op == "AND" else query.Or(sdk_filters)

        raise TypeError(f"Unknown node type: {type(node)}")

    def _build(self) -> query.Query:
        """Helper to prepare the native SDK Query object."""
        self._warn_for_unindexed_properties()

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
    ) -> "Model | Any":
        """Shared logic to convert a raw Datastore entity into a Key or a Model."""
        if keys_only:
            return entity.key
        return self.model_cls.from_entity(entity, _is_projected=is_projected)

    def fetch(self, limit: int | None = None) -> "Generator[Model | datastore.Key, None, None]":
        """Executes the query and yields results.

        Args:
            limit (int | None): The maximum number of results to return.

        Yields:
            Model | datastore.Key: Hydrated model instances, or Datastore Keys
            if `keys_only()` was called.

        Examples:
            ```python
            for user in User.query().filter(User.age > 18).fetch(limit=50):
                print(user.name)
            ```
        """
        native_query = self._build()
        is_projected = bool(self._projection)

        def _generator() -> "Generator[Model | datastore.Key, None, None]":
            for entity in native_query.fetch(limit=limit):
                yield self._hydrate_entity(
                    entity=entity,
                    keys_only=self._keys_only,
                    is_projected=is_projected
                )

        return _generator()

    def fetch_page(
            self,
            page_size: int,
            start_cursor: bytes | None = None
    ) -> "tuple[list[Model | datastore.Key], bytes | None, bool]":
        """Fetches a specific page of results, returning metadata needed for pagination.

        Args:
            page_size (int): The maximum number of entities to retrieve in this page.
            start_cursor (bytes | None): The pagination cursor from a previous call.

        Returns:
            A tuple containing three elements `(results, next_cursor, has_more)`

                - `results`: A list of hydrated instances (or Keys).
                - `next_cursor`: The byte string cursor for the next page, or `None` if finished.
                - `has_more`: `True` if there are more entities remaining, otherwise `False`.


        Examples:
            ```python
            q = User.query().order(User.name)

            cursor = None
            while True:
                page, cursor, has_more = q.fetch_page(page_size=20, start_cursor=cursor)
                process_users(page)

                if not has_more:
                    break
            ```
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

    def get(self) -> "Model | datastore.Key | None":
        """Executes the query and returns the first matching result.

        Automatically applies a `limit=1` to the query to ensure maximum efficiency.

        Returns:
            Model | datastore.Key | None: The first matching instance, or `None` if
                the query returned zero results.

        Examples:
            ```python
            first_admin = User.query().filter(User.role == "admin").get()
            ```
        """
        results = list(self.fetch(limit=1))
        return results[0] if results else None

    def count(self) -> int:
        """Performs a fast server-side count aggregation.

        This delegates the counting operation to Google's backend, making it infinitely
        more scalable and cost-effective than fetching and counting entities locally.

        Returns:
            int: The total number of matching entities.
        """
        client = get_client(self.project, self.database)
        agg_query = client.aggregation_query(self._build())
        agg_query.add_aggregation(Count())

        results = list(agg_query.fetch())
        return results[0][0].value if results else 0

    def sum(self, property_field: "str | Property") -> int | float:
        """Performs a fast server-side sum aggregation on a specific property.

        Args:
            property_field (str | Property): The property to sum.

        Returns:
            int | float: The total sum. Returns 0 if no entities matched.
        """
        prop_name = getattr(property_field, 'datastore_name', property_field)

        client = get_client(self.project, self.database)
        agg_query = client.aggregation_query(self._build())
        agg_query.add_aggregation(Sum(prop_name))

        results = list(agg_query.fetch())
        return results[0][0].value if results and results[0] else 0

    def avg(self, property_field: "str | Property") -> float | None:
        """Performs a fast server-side average aggregation on a specific property.

        Args:
            property_field (str | Property): The property to average.

        Returns:
            float | None: The average value, or `None` if no entities matched.
        """
        prop_name = getattr(property_field, 'datastore_name', property_field)

        client = get_client(self.project, self.database)
        agg_query = client.aggregation_query(self._build())
        agg_query.add_aggregation(Avg(prop_name))

        results = list(agg_query.fetch())
        return results[0][0].value if results and results[0] else None

    def aggregate(self, **kwargs: Count | Sum | Avg) -> dict[str, Any]:
        """Performs multiple aggregations in a single Datastore RPC call.

        Args:
            **kwargs: Alias names mapped to Google Datastore Aggregation objects
                (`Count`, `Sum`, or `Avg`).

        Returns:
            dict[str, Any]: A dictionary mapping your aliases to their aggregated values.

        Examples:
            ```python
            from google.cloud.datastore.aggregation import CountAggregation as Count
            from google.cloud.datastore.aggregation import SumAggregation as Sum

            stats = Article.query().aggregate(
                total_articles=Count(),
                total_views=Sum(Article.views)
            )
            print(stats["total_views"])
            ```
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
