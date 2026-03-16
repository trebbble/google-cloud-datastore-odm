from tests.conftest import QueryTestModel


def test_persistence(reset_datastore, query_model_instance):
    stored = query_model_instance.put()
    retrieved = QueryTestModel.get(stored.key)

    assert retrieved is not None
    assert stored.key.id == retrieved.key.id
    assert stored.name == retrieved.name
    assert stored.age == retrieved.age


def test_query_filter_single(reset_datastore, query_model_instance):
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


def test_query_filter_multiple(reset_datastore, query_model_instance):
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
