import pytest

from src.google_cloud_datastore_odm.client import get_client
from src.google_cloud_datastore_odm.model import Model
from src.google_cloud_datastore_odm.properties import Property, StringProperty, IntegerProperty


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
    assert model.key is None
    model.allocate_key()
    assert model.key is not None


def test_id_property():
    model = KeyTestModel(name="test")
    assert model.key is None

    client = get_client()
    model.key = client.key("KeyTestModel", 123)
    assert model.key.id == 123
    
    model.key = client.key("KeyTestModel", "named_key")
    assert model.key.name == "named_key"


def test_key_from_id_and_get_by_id(reset_datastore):
    key = KeyTestModel.key_from_id(123)
    assert key.id == 123
    assert key.kind == "KeyTestModel"
    
    model = KeyTestModel(name="test", key=key)
    model.put()
    
    fetched = KeyTestModel.get_by_id(123)
    assert fetched is not None
    assert fetched.name == "test"
    assert fetched.key.id == 123


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


def test_metaclass_rejects_reserved_property_names():
    """Ensure the ODM protects its internal identity attributes."""

    with pytest.raises(ValueError):
        class BadModelKey(Model):
            key = StringProperty()


def test_metaclass_allows_aliased_reserved_names():
    """Ensure developers can still map to legacy datastore fields using aliases."""

    class ValidModel(Model):
        custom_id = StringProperty(name="id")
        custom_key = StringProperty(name="key")

    assert "custom_id" in ValidModel.get_schema(output_format='property_names')
    assert ValidModel.get_schema(output_format='property_aliases')["custom_id"] == "id"
    assert ValidModel.get_schema(output_format='named_properties')["custom_key"].datastore_name == "key"


def test_model_init_reserved_kwargs_routing():
    """Ensure id, parent, and key kwargs are correctly routed to Datastore Keys."""

    class TestNode(Model):
        __kind__ = "TestNode"
        value = StringProperty()

    node1 = TestNode(id="my-node-1", value="test")
    assert node1.key is not None
    assert node1.key.name == "my-node-1"

    client = get_client()

    parent_key = client.key("ParentKind", "parent-1")
    node2 = TestNode(parent=parent_key, value="test")
    assert node2.key is not None
    assert node2.key.parent == parent_key
    assert node2.key.is_partial is True
    assert node2.key.parent == parent_key

    node3 = TestNode(id=999, parent=parent_key, value="test")
    assert node3.key.id == 999
    assert node3.key.parent == parent_key

    explicit_key = client.key("TestNode", "explicit")
    node4 = TestNode(key=explicit_key, value="test")
    assert node4.key == explicit_key
    assert node4.key.name == "explicit"


def test_model_init_unknown_kwargs():
    """Ensure passing random kwargs still raises a strict schema error."""

    class StrictModel(Model):
        name = StringProperty()

    with pytest.raises(AttributeError):
        StrictModel(name="Alice", typo_field="value")


def test_unreserved_metadata_kwarg():
    """Ensure passing 'id' directly works if no 'id' property is defined."""

    class NoIdModel(Model):
        __kind__ = "NoId"
        name = StringProperty()

    instance = NoIdModel(id=444, name="Test")
    assert instance.key is not None
    assert instance.key.id == 444
    assert instance.name == "Test"


def test_reserved_metadata_kwarg():
    """Ensure passing '_id' directly works if 'id' property is defined."""

    class NoIdModel(Model):
        __kind__ = "NoId"
        id = IntegerProperty()
        name = StringProperty()

    instance = NoIdModel(_id=444, name="Test")
    assert instance.key is not None
    assert instance.key.id == 444
    assert instance.name == "Test"


def test_repr_numeric_id():
    """Ensure __repr__ formats correctly when the key uses a numeric ID."""

    class ReprModel(Model):
        __kind__ = "Repr"
        val = IntegerProperty()

    instance = ReprModel(id=123, val=5)

    repr_str = repr(instance)
    assert "id=123" in repr_str
    assert "val=5" in repr_str

    instance = ReprModel(id='123', val=5)
    repr_str = repr(instance)
    assert "id='123'" in repr_str
    assert "val=5" in repr_str


def test_to_dict_include_exclude():
    """Ensure to_dict correctly skips properties based on include/exclude lists."""

    class FilterModel(Model):
        a = StringProperty()
        b = StringProperty()
        c = StringProperty()

    instance = FilterModel(a="apple", b="banana", c="cherry")

    included = instance.to_dict(include=["a", "c"])
    assert included == {"a": "apple", "c": "cherry"}
    assert "b" not in included

    excluded = instance.to_dict(exclude=["b"])
    assert excluded == {"a": "apple", "c": "cherry"}
    assert "b" not in excluded


def test_populate_unknown_property():
    """Ensure populate raises AttributeError for non-existent properties."""

    class PopModel(Model):
        name = StringProperty()

    instance = PopModel(name="Initial")

    instance.populate(name="Updated")
    assert instance.name == "Updated"

    with pytest.raises(AttributeError, match="Unknown property: invalid_field"):
        instance.populate(invalid_field="Value")


def test_put_exclude_from_indexes_emulator(reset_datastore):
    """Ensure put() correctly merges schema-level and instance-level index exclusions in Datastore."""

    class IndexTestModel(Model):
        __kind__ = "IndexTest"
        normal = StringProperty()
        always_unindexed = StringProperty(indexed=False)
        dynamic_unindexed = StringProperty(name="dynamic_db_name")

    assert frozenset(["always_unindexed"]) == IndexTestModel._unindexed_datastore_names

    client = get_client()

    instance = IndexTestModel(
        normal="A",
        always_unindexed="B",
        dynamic_unindexed="C"
    )

    instance.put(exclude_from_indexes=["dynamic_unindexed"])

    raw_entity = client.get(instance.key)
    assert raw_entity is not None

    exclusions = raw_entity.exclude_from_indexes
    assert "always_unindexed" in exclusions
    assert "dynamic_db_name" in exclusions
    assert "normal" not in exclusions

    instance.put(exclude_from_indexes=["dynamic_db_name"])

    raw_entity = client.get(instance.key)
    assert raw_entity is not None

    exclusions = raw_entity.exclude_from_indexes
    assert "always_unindexed" in exclusions
    assert "dynamic_db_name" in exclusions
    assert "normal" not in exclusions

    instance.put(exclude_from_indexes=["dynamic_unindexed", "normal", "random_field_no_property_no_alias"])

    raw_entity = client.get(instance.key)
    assert raw_entity is not None

    exclusions = raw_entity.exclude_from_indexes
    assert "always_unindexed" in exclusions
    assert "dynamic_db_name" in exclusions
    assert "normal" in exclusions
    assert "random_field_no_property_no_alias" not in exclusions
