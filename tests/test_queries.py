from unittest.mock import MagicMock, patch

import pytest
from google.cloud.datastore import Key, query

from src.google_cloud_datastore_odm import AND, OR, IntegerProperty, Model, StringProperty
from src.google_cloud_datastore_odm.query import CompositeNode, FilterNode, Node, OrderNode, Query
from tests.conftest import QueryTestModel


class ASTUser(Model):
    name = StringProperty()
    age = IntegerProperty()
    role = StringProperty(name="db_role")


@pytest.fixture
def seed_data(reset_datastore):
    """Fixture to seed multiple entities for advanced querying."""
    QueryTestModel(name="Alice", age=25).put()
    QueryTestModel(name="Bob", age=30).put()
    QueryTestModel(name="Charlie", age=35).put()
    QueryTestModel(name="Alice", age=40).put()


def test_persistence(reset_datastore, query_model_instance):
    stored_key = query_model_instance.put()
    retrieved = QueryTestModel.get(stored_key)

    assert retrieved is not None
    assert stored_key.id == retrieved.key.id
    assert query_model_instance.name == retrieved.name
    assert query_model_instance.age == retrieved.age


def test_query_filter_raw_single(reset_datastore, query_model_instance):
    query_model_instance.put()

    results = list(
        QueryTestModel.query()
        .filter("age", "=", 30)
        .fetch()
    )

    assert len(results) == 1
    result: QueryTestModel = results[0]
    assert result.name == "Bob"
    assert result.age == 30


def test_query_filter_raw_multiple(reset_datastore, query_model_instance):
    query_model_instance.put()

    results = list(
        QueryTestModel.query()
        .filter("age", "=", 30)
        .filter("name", "=", "Bob")
        .fetch()
    )

    assert results
    first: QueryTestModel = results[0]
    assert first.name == "Bob"
    assert first.age == 30


def test_query_limit(reset_datastore):
    for index in range(5):
        QueryTestModel(name=f"User{index}", age=index).put()

    results = list(QueryTestModel.query().fetch(limit=3))
    assert len(results) == 3


def test_ast_filter_nodes():
    """Test that magic methods generate the correct FilterNodes."""
    node_eq = ASTUser.name == "Alice"
    assert isinstance(node_eq, FilterNode)
    assert node_eq.name == "name"
    assert node_eq.op == "="
    assert node_eq.value == "Alice"

    node_gt = ASTUser.age > 21
    assert node_gt.name == "age"
    assert node_gt.op == ">"
    assert node_gt.value == 21

    node_in = ASTUser.name.in_(["Alice", "Bob"])
    assert node_in.name == "name"
    assert node_in.op == "IN"
    assert node_in.value == ["Alice", "Bob"]

    node_mapped = ASTUser.role == "admin"
    assert node_mapped.name == "db_role"


def test_ast_order_nodes():
    """Test that unary operators generate the correct OrderNodes."""
    desc_node = -ASTUser.age
    assert isinstance(desc_node, OrderNode)
    assert desc_node.name == "age"
    assert desc_node.descending is True

    asc_node = +ASTUser.name
    assert isinstance(asc_node, OrderNode)
    assert asc_node.name == "name"
    assert asc_node.descending is False

    desc_node = -ASTUser.role
    assert isinstance(asc_node, OrderNode)
    assert desc_node.name == "db_role"
    assert desc_node.descending is True


def test_ast_composite_nodes():
    """Test that bitwise and explicit logic functions build CompositeNodes."""
    node_and = (ASTUser.name == "Alice") & (ASTUser.age == 30)
    assert isinstance(node_and, CompositeNode)
    assert node_and.op == "AND"
    assert len(node_and.filters) == 2

    node_or = OR(ASTUser.age < 18, ASTUser.age >= 65)
    assert node_or.op == "OR"
    assert len(node_or.filters) == 2


def test_ast_translation():
    """Test that our AST nodes translate perfectly into native SDK objects."""
    base_query = Query(model_cls=ASTUser)

    sdk_filter = base_query._translate(ASTUser.name == "Bob")
    assert isinstance(sdk_filter, query.PropertyFilter)
    assert sdk_filter.property_name == "name"
    assert sdk_filter.operator == "="
    assert sdk_filter.value == "Bob"

    node = OR(
        AND(ASTUser.name == "Bob", ASTUser.age > 20),
        ASTUser.role == "admin"
    )
    sdk_composite = base_query._translate(node)

    assert isinstance(sdk_composite, query.Or)
    assert len(sdk_composite.filters) == 2
    assert isinstance(sdk_composite.filters[0], query.And)
    assert isinstance(sdk_composite.filters[1], query.PropertyFilter)
    assert sdk_composite.filters[1].property_name == "db_role"


def test_odm_style_equality_and_inequality(seed_data):
    alices: list[QueryTestModel] = list(QueryTestModel.query().filter(QueryTestModel.name == "Alice").fetch())
    assert len(alices) == 2
    assert all(a.name == "Alice" for a in alices)

    older_users: list[QueryTestModel] = list(QueryTestModel.query().filter(QueryTestModel.age >= 35).fetch())
    assert len(older_users) == 2
    assert {u.name for u in older_users} == {"Charlie", "Alice"}


def test_odm_style_in_operator(seed_data):
    results: list[QueryTestModel] = list(QueryTestModel.query().filter(QueryTestModel.age.in_([25, 35])).fetch())
    assert len(results) == 2
    assert {u.name for u in results} == {"Alice", "Charlie"}


def test_odm_style_or_operator(seed_data):
    results: list[QueryTestModel] = list(
        QueryTestModel.query()
        .filter(OR(QueryTestModel.name == "Bob", QueryTestModel.age == 40))
        .fetch()
    )
    assert len(results) == 2
    assert {u.name for u in results} == {"Bob", "Alice"}


def test_odm_style_bitwise_operators(seed_data):
    results: list[QueryTestModel] = list(
        QueryTestModel.query().filter(
            ((QueryTestModel.name == "Alice") & (QueryTestModel.age == 25)) | (QueryTestModel.name == "Bob")
        ).fetch()
    )
    assert len(results) == 2
    assert {u.age for u in results} == {25, 30}


def test_odm_style_ordering(seed_data):
    results: list[QueryTestModel] = list(QueryTestModel.query().order(-QueryTestModel.age).fetch())
    assert len(results) == 4
    assert results[0].age == 40
    assert results[-1].age == 25


def test_odm_style_count_aggregation(seed_data):
    total_users = QueryTestModel.query().count()
    assert total_users == 4

    alice_count = QueryTestModel.query().filter(QueryTestModel.name == "Alice").count()
    assert alice_count == 2


def test_ast_comparison_operators():
    assert (ASTUser.age == 20).op == "="
    assert (ASTUser.age != 20).op == "!="
    assert (ASTUser.age < 20).op == "<"
    assert (ASTUser.age > 20).op == ">"
    assert (ASTUser.age <= 20).op == "<="
    assert (ASTUser.age >= 20).op == ">="
    assert (ASTUser.name.IN(["Alice", "Bob"])).op == "IN"
    assert (ASTUser.name.in_(["Alice", "Bob"])).op == "IN"
    assert (ASTUser.age.NOT_IN(["Alice", "Bob"])).op == "NOT_IN"
    assert (ASTUser.age.not_in_(["Alice", "Bob"])).op == "NOT_IN"


def test_ast_not_in_and_type_errors():
    """Covers not_in_ and the TypeErrors for non-iterables when using operators IN/NOT_IN."""
    with pytest.raises(TypeError, match="requires an iterable"):
        ASTUser.name.in_("not a list")

    with pytest.raises(TypeError, match="requires an iterable"):
        ASTUser.name.not_in_(123)


def test_query_filter_invalid_argument():
    """Covers the ValueError fallback in Query.filter() when passed bad types."""
    with pytest.raises(ValueError, match="Invalid filter"):
        ASTUser.query().filter(123)


def test_query_order_raw_strings_and_properties():
    """Covers the raw string and raw Property fallbacks in Query.order()."""
    q = ASTUser.query().order("-age", "name", ASTUser.role)

    assert len(q._orders) == 3

    assert q._orders[0].name == "age"
    assert q._orders[0].descending is True

    assert q._orders[1].name == "name"
    assert q._orders[1].descending is False

    assert q._orders[2].name == "db_role"
    assert q._orders[2].descending is False


def test_query_translate_unknown_node():
    """Covers the TypeError fallback in Query._translate() for unknown nodes."""

    class DummyNode(Node):
        """A fake node that doesn't inherit from FilterNode or CompositeNode."""
        pass

    with pytest.raises(TypeError, match="Unknown node type"):
        Query(model_cls=ASTUser)._translate(DummyNode())


def test_query_keys_only(seed_data):
    """Ensure keys_only=True returns Datastore Keys instead of Model instances."""
    results = list(QueryTestModel.query().keys_only().fetch())

    assert len(results) == 4
    for result in results:
        assert isinstance(result, Key)
        assert result.kind == QueryTestModel.kind()


def test_query_projection(seed_data):
    """Ensure projection queries return partial models and block unrequested fields."""
    results = list(QueryTestModel.query().projection("name").fetch())

    assert len(results) == 4
    for result in results:
        assert isinstance(result, QueryTestModel)
        assert getattr(result, "_is_projected", False) is True
        assert result.name in ["Alice", "Bob", "Charlie"]

        with pytest.raises(AttributeError):
            _ = result.age

        with pytest.raises(RuntimeError):
            result.age = 25
            result.put()


def test_query_distinct(seed_data):
    """Ensure distinct_on filters out duplicate rows based on the projection."""
    unique_authors = list(
        QueryTestModel.query().projection(QueryTestModel.name).distinct_on(QueryTestModel.name).fetch()
    )

    assert len(unique_authors) == 3
    names = {r.name for r in unique_authors}
    assert names == {"Alice", "Bob", "Charlie"}


def test_query_get(seed_data):
    """Ensure Query.get() returns the first match or None, and respects projections."""
    alice = QueryTestModel.query().filter(QueryTestModel.name == "Alice").get()
    assert isinstance(alice, QueryTestModel)
    assert alice.name == "Alice"
    assert alice.age in [25, 40]

    nobody = QueryTestModel.query().filter(QueryTestModel.name == "Zebra").get()
    assert nobody is None

    projected_bob: QueryTestModel = QueryTestModel.query().filter(QueryTestModel.name == "Bob"
                                                                  ).projection(QueryTestModel.age).get()
    assert getattr(projected_bob, "_is_projected", False) is True
    assert projected_bob.age == 30

    with pytest.raises(AttributeError):
        _ = projected_bob.name


def test_query_build_projection_mapping():
    """Ensure _build correctly maps Property descriptors to Datastore names."""
    q = ASTUser.query().projection(ASTUser.role, "name")

    native_query = q._build()
    assert native_query.projection == ["db_role", "name"]

    q = ASTUser.query().projection(ASTUser.role, "name").distinct_on("db_role", ASTUser.name)
    native_distinct = q._build()
    assert native_distinct.distinct_on == ["db_role", "name"]


def test_query_fetch_page_lifecycle(seed_data):
    """Ensure fetch_page correctly paginates through results using cursors."""
    q = QueryTestModel.query().order("age")

    page_1, cursor_1, has_more_1 = q.fetch_page(page_size=2)
    assert len(page_1) == 2
    assert page_1[0].age == 25
    assert page_1[1].age == 30
    assert has_more_1 is True
    assert cursor_1 is not None

    page_2, cursor_2, has_more_2 = q.fetch_page(page_size=2, start_cursor=cursor_1)
    assert len(page_2) == 2
    assert page_2[0].age == 35
    assert page_2[1].age == 40

    assert has_more_2 is False
    assert cursor_2 is None


def test_query_fetch_all_in_one_page(seed_data):
    page, cursor, has_more = QueryTestModel.query().fetch_page(page_size=5)

    assert len(page) == 4
    assert has_more is False
    assert cursor is None


def test_query_fetch_page_keys_only(seed_data):
    """Ensure fetch_page respects keys_only."""
    page, cursor, has_more = QueryTestModel.query().keys_only().fetch_page(page_size=3)

    assert len(page) == 3
    assert isinstance(page[0], Key)
    assert has_more is True
    assert cursor is not None


def test_query_fetch_page_stop_iteration():
    """Ensure fetch_page safely catches StopIteration if the SDK returns zero pages."""
    q = QueryTestModel.query()

    # Create a mock native query where the 'pages' property is an empty generator
    mock_native_query = MagicMock()
    mock_native_query.fetch.return_value.pages = iter([])

    # Patch the _build method to return our mock instead of a real SDK query
    with patch.object(q, '_build', return_value=mock_native_query):
        page, cursor, has_more = q.fetch_page(page_size=10)

    # Assert the fallback block worked perfectly
    assert page == []
    assert cursor is None
    assert has_more is False
