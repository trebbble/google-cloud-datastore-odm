import pytest
from src.google_cloud_datastore_odm.model import Model
from src.google_cloud_datastore_odm.fields import StringField, IntegerField


class Constants:
    STRING_DEFAULT = 'default'
    INTEGER_DEFAULT = 0

    STRING_FIXTURE = 'test'
    INTEGER_FIXTURE = 1


class DymmyTestModel(Model):
    test_string_field = StringField(required=True, default=Constants.STRING_DEFAULT)
    test_integer_field = IntegerField(required=True, default=Constants.INTEGER_DEFAULT)


@pytest.fixture
def sample_doc() -> DymmyTestModel:
    return DymmyTestModel(test_string_field=Constants.STRING_FIXTURE, test_integer_field=Constants.INTEGER_FIXTURE)


def test_attribute_assignment_and_getattr(sample_doc):
    assert sample_doc.test_string_field == Constants.STRING_FIXTURE
    assert sample_doc.test_integer_field == Constants.INTEGER_FIXTURE

    sample_doc.test_integer_field = 30
    assert sample_doc.test_integer_field == 30


def test_dict_style_access(sample_doc):
    assert sample_doc["test_string_field"] == Constants.STRING_FIXTURE
    assert sample_doc["test_integer_field"] == Constants.INTEGER_FIXTURE

    sample_doc["test_integer_field"] = 35
    assert sample_doc.test_integer_field == 35


def test_iteration_and_items(sample_doc):
    keys = list(sample_doc)
    assert "test_string_field" in keys
    assert "test_integer_field" in keys

    items = dict(sample_doc.items())
    assert items["test_string_field"] == Constants.STRING_FIXTURE
    assert items["test_integer_field"] == Constants.INTEGER_FIXTURE


def test_missing_required_field_raises():
    class Dummy(Model):
        test_string_field = StringField(required=True)

    with pytest.raises(ValueError):
        Dummy()
