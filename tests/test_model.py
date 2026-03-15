import pytest

from src.google_cloud_datastore_odm.client import get_client
from src.google_cloud_datastore_odm.model import Model
from src.google_cloud_datastore_odm.properties import Property, StringProperty


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

    client = get_client()
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


def test_datastore_alias_and_indexing(reset_datastore):
    class AliasModel(Model):
        __kind__ = "AliasModel"
        python_name = StringProperty(name="ds_alias")
        unindexed_text = StringProperty(indexed=False, name="ds_unindexed")

    instance = AliasModel(python_name="hello", unindexed_text="world")
    instance.put()

    assert instance.python_name == "hello"
    assert not hasattr(instance, "ds_alias")
    assert "ds_alias" not in instance.to_dict()

    client = get_client()
    raw_entity = client.get(instance.key)

    assert "ds_alias" in raw_entity
    assert raw_entity["ds_alias"] == "hello"
    assert "python_name" not in raw_entity

    assert "ds_unindexed" in raw_entity.exclude_from_indexes
    assert "ds_alias" not in raw_entity.exclude_from_indexes


def test_strict_schema_kwargs():
    class StrictModel(Model):
        name = StringProperty()

    with pytest.raises(AttributeError):
        StrictModel(name="test", unknown_field="boom")


def test_uncopyable_default():
    import threading
    lock = threading.Lock()  # Thread locks cannot be pickled/deepcopied

    class UncopyableModel(Model):
        bad_default = Property(default=lock)

    instance = UncopyableModel()
    assert instance.bad_default is lock


def test_init_with_explicit_id(reset_datastore):

    class IdModel(Model):
        __kind__ = "IdModel"
        name = StringProperty()

    instance = IdModel(id=999, name="Test ID")

    assert instance.key is not None
    assert instance.key.id == 999
    assert instance.id == 999


def test_init_with_callable_default():

    def generate_dynamic_string():
        return "dynamically_generated"

    class CallableDefaultModel(Model):
        dynamic_field = StringProperty(default=generate_dynamic_string)

    instance = CallableDefaultModel()

    assert instance.dynamic_field == "dynamically_generated"


def test_get_schema_formats():

    def dynamic_default(): pass

    class SchemaTestModel(Model):
        title = StringProperty(required=True)
        author = StringProperty(name="author_name", default="Anonymous")
        dynamic = StringProperty(default=dynamic_default)

    props_list = SchemaTestModel.get_schema("properties")
    assert isinstance(props_list, list)
    assert len(props_list) == 3
    assert hasattr(props_list[0], "datastore_name")

    names = SchemaTestModel.get_schema("property_names")
    assert names == ["title", "author", "dynamic"]

    named_props = SchemaTestModel.get_schema("named_properties")
    assert isinstance(named_props, dict)
    assert named_props["title"].required is True

    aliases = SchemaTestModel.get_schema("property_aliases")
    assert aliases == {"title": "title", "author": "author_name", "dynamic": "dynamic"}

    full_schema = SchemaTestModel.get_schema()
    assert isinstance(full_schema, dict)
    assert full_schema["title"]["type"] == "StringProperty"
    assert full_schema["title"]["required"] is True
    assert full_schema["author"]["datastore_name"] == "author_name"
    assert full_schema["author"]["default"] == "Anonymous"
    assert full_schema["dynamic"]["default"] == "<callable: dynamic_default>"

    with pytest.raises(ValueError):
        SchemaTestModel.get_schema("not_a_real_format")
