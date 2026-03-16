from tests.conftest import QueryTestModel


def test_persistence(reset_datastore, query_model_instance):
    stored_key = query_model_instance.put()
    retrieved = QueryTestModel.get(stored_key)

    assert retrieved is not None
    assert stored_key.id == retrieved.key.id
    assert query_model_instance.name == retrieved.name
    assert query_model_instance.age == retrieved.age


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
