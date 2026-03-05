import pytest

from src.google_cloud_datastore_odm.model import Model
from src.google_cloud_datastore_odm.fields import StringField, IntegerField


class QueryModel(Model):
    __kind__ = "QueryModel"

    name = StringField()
    age = IntegerField()


@pytest.fixture
def query_model_instance():
    return QueryModel(name="Bob", age=30)


def test_persistence(reset_datastore, query_model_instance):
    stored = query_model_instance.put()
    retrieved = QueryModel.get(stored.key)

    assert retrieved is not None
    assert stored.id == retrieved.id
    assert stored.name == retrieved.name
    assert stored.age == retrieved.age


def test_query_filter_single(reset_datastore, query_model_instance):
    query_model_instance.put()

    results = list(
        QueryModel.query()
        .filter("age", "=", 30)
        .fetch()
    )

    assert len(results) == 1
    result: QueryModel = results[0]
    assert result.name == "Bob"
    assert result.age == 30


def test_query_filter_multiple(reset_datastore, query_model_instance):
    query_model_instance.put()

    results = list(
        QueryModel.query()
        .filter("age", "=", 30)
        .filter("name", "=", "Bob")
        .fetch()
    )

    assert results
    first: QueryModel = results[0]
    assert first.name == "Bob"
    assert first.age == 30


def test_query_limit(reset_datastore):
    for index in range(5):
        QueryModel(name=f"User{index}", age=index).put()

    results = list(QueryModel.query().fetch(limit=3))
    assert len(results) == 3
