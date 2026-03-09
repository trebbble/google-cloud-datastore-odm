import pytest

from src.google_cloud_datastore_odm.fields import StringField
from src.google_cloud_datastore_odm.model import Model
from tests.conftest import Constants


def test_attribute_assignment_and_getattr(sample_dummy_doc):
    assert sample_dummy_doc.test_string_field == Constants.STRING_FIXTURE
    assert sample_dummy_doc.test_integer_field == Constants.INTEGER_FIXTURE

    sample_dummy_doc.test_integer_field = 30
    assert sample_dummy_doc.test_integer_field == 30


def test_dict_style_access(sample_dummy_doc):
    assert sample_dummy_doc["test_string_field"] == Constants.STRING_FIXTURE
    assert sample_dummy_doc["test_integer_field"] == Constants.INTEGER_FIXTURE

    sample_dummy_doc["test_integer_field"] = 35
    assert sample_dummy_doc.test_integer_field == 35


def test_iteration_and_items(sample_dummy_doc):
    keys = list(sample_dummy_doc)
    assert "test_string_field" in keys
    assert "test_integer_field" in keys

    items = dict(sample_dummy_doc.items())
    assert items["test_string_field"] == Constants.STRING_FIXTURE
    assert items["test_integer_field"] == Constants.INTEGER_FIXTURE


def test_missing_required_field_raises():
    class Dummy(Model):
        test_string_field = StringField(required=True)

    with pytest.raises(ValueError):
        Dummy()
