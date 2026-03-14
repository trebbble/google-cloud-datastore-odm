import pytest

from src.google_cloud_datastore_odm.model import Model
from src.google_cloud_datastore_odm.properties import StringProperty


class KeyTestModel(Model):
    name = StringProperty()


def test_model_invalid_kind():
    with pytest.raises(TypeError):
        class InvalidKindModel(Model):
            __kind__ = 123


def test_model_repr_with_key():
    model = KeyTestModel(name="test")
    assert "id=None" not in repr(model)
    
    model.allocate_key()
    assert repr(model).startswith("<KeyTestModel id=")


def test_model_to_dict():
    model = KeyTestModel(name="test")
    d = model.to_dict()
    assert isinstance(d, dict)
    assert d["name"] == "test"
    assert model._values is not d


def test_has_key():
    model = KeyTestModel(name="test")
    assert not model.has_key
    model.allocate_key()
    assert model.has_key


def test_id_property():
    model = KeyTestModel(name="test")
    assert model.id is None
    
    client = KeyTestModel._client()
    model.key = client.key("KeyTestModel", 123)
    assert model.id == 123
    
    model.key = client.key("KeyTestModel", "named_key")
    assert model.id == "named_key"


def test_key_from_id_and_get_by_id(reset_datastore):
    key = KeyTestModel.key_from_id(123)
    assert key.id == 123
    assert key.kind == "KeyTestModel"
    
    model = KeyTestModel(name="test", key=key)
    model.put()
    
    fetched = KeyTestModel.get_by_id(123)
    assert fetched is not None
    assert fetched.name == "test"
    assert fetched.id == 123


def test_from_entity_none():
    assert KeyTestModel.from_entity(None) is None


def test_model_invalid_validator_not_callable():
    with pytest.raises(TypeError):
        class Mock(object):
            pass

        class InvalidValidator(Model):
            
            mock = Mock()
            mock.__model_validator__ = True
