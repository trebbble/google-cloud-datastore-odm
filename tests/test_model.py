import datetime

import pytest
from google.cloud import datastore

from google_cloud_datastore_odm.client import get_client
from google_cloud_datastore_odm.model import Model, field_validator
from google_cloud_datastore_odm.properties import DateProperty, IntegerProperty, Property, StringProperty


class KeyTestModel(Model):
    name = StringProperty()


def test_model_invalid_kind():
    with pytest.raises(TypeError):

        class InvalidKindModel(Model):
            class Meta:
                kind = 123


def test_model_repr_with_key():
    model = KeyTestModel(name="test")
    assert "id=None" not in repr(model)

    model.allocate_key()
    assert "id=" in repr(model)


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

    def dynamic_default():
        pass

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

    assert "custom_id" in ValidModel.get_schema(output_format="property_names")
    assert ValidModel.get_schema(output_format="property_aliases")["custom_id"] == "id"
    assert ValidModel.get_schema(output_format="named_properties")["custom_key"].datastore_name == "key"


def test_model_init_reserved_kwargs_routing():
    """Ensure id, parent, and key kwargs are correctly routed to Datastore Keys."""

    class TestNode(Model):
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
        name = StringProperty()

        class Meta:
            kind = "NoId"

    instance = NoIdModel(id=444, name="Test")
    assert instance.key is not None
    assert instance.key.id == 444
    assert instance.name == "Test"


def test_reserved_metadata_kwarg():
    """Ensure passing '_id' directly works if 'id' property is defined."""

    class NoIdModel(Model):
        id = IntegerProperty()
        name = StringProperty()

        class Meta:
            kind = "NoId"

    instance = NoIdModel(_id=444, name="Test")
    assert instance.key is not None
    assert instance.key.id == 444
    assert instance.name == "Test"


def test_repr_numeric_id():
    """Ensure __repr__ formats correctly when the key uses a numeric ID."""

    class ReprModel(Model):
        val = IntegerProperty()

        class Meta:
            kind = "Repr"

    instance = ReprModel(id=123, val=5)

    repr_str = repr(instance)
    assert "id=123" in repr_str
    assert "val=5" in repr_str

    instance = ReprModel(id="123", val=5)
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


def test_populate_happy_path():
    """Ensure populate updates multiple valid properties simultaneously."""

    class PopModel(Model):
        name = StringProperty()
        age = IntegerProperty()

    instance = PopModel(name="Alice", age=30)
    assert instance.name == "Alice"
    assert instance.age == 30

    instance.populate(name="Bob", age=31)

    assert instance.name == "Bob"
    assert instance.age == 31


def test_populate_failures():
    """Ensure populate blocks unknown properties and respects validators."""

    class PopModel(Model):
        name = StringProperty()
        age = IntegerProperty()

        @field_validator("age")
        def validate_adult(self, value: int) -> int:
            if value < 18:
                raise ValueError("Only adults are allowed.")
            return value

    instance = PopModel(name="Alice", age=30)

    with pytest.raises(TypeError):
        instance.populate(age="thirty-one")

    with pytest.raises(ValueError):
        instance.populate(age=17)

    assert instance.name == "Alice"
    assert instance.age == 30

    with pytest.raises(TypeError):
        _ = PopModel(name="Alice", age="thirty-one")

    with pytest.raises(ValueError):
        _ = PopModel(name="Alice", age=17)


def test_populate_unknown_property():
    """Ensure populate raises AttributeError for non-existent properties."""

    class PopModel(Model):
        name = StringProperty()

    instance = PopModel(name="Initial")

    instance.populate(name="Updated")
    assert instance.name == "Updated"

    with pytest.raises(AttributeError):
        instance.populate(invalid_field="Value")


def test_put_exclude_from_indexes_emulator(reset_datastore):
    """Ensure put() correctly merges schema-level and instance-level index exclusions in Datastore."""

    class IndexTestModel(Model):
        normal = StringProperty()
        always_unindexed = StringProperty(indexed=False)
        dynamic_unindexed = StringProperty(name="dynamic_db_name")

        class Meta:
            kind = "IndexTest"

    assert frozenset(["always_unindexed"]) == IndexTestModel._unindexed_datastore_names

    client = get_client()

    instance = IndexTestModel(normal="A", always_unindexed="B", dynamic_unindexed="C")

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


def test_model_equality():
    """Ensure __eq__ strictly compares both keys and underlying values (NDB style)."""

    class EqModel(Model):
        name = StringProperty()

    m1 = EqModel(name="Alice")
    m2 = EqModel(name="Alice")
    assert m1 == m2

    m3 = EqModel(name="Bob")
    assert m1 != m3

    shared_key = EqModel.key_from_id(1)
    m4 = EqModel(key=shared_key, name="Charlie")
    m5 = EqModel(key=shared_key, name="Charlie")
    assert m4 == m5

    m6 = EqModel(key=shared_key, name="David")
    assert m4 != m6

    diff_key = EqModel.key_from_id(2)
    m7 = EqModel(key=diff_key, name="Charlie")
    assert m4 != m7

    assert m1 != m4

    assert m1 != "Some String"


def test_model_delete(reset_datastore):
    """Ensure single instance deletion works against the emulator."""

    class DeleteModel(Model):
        name = StringProperty()

    instance = DeleteModel(name="To Be Deleted")
    key = instance.put()

    assert DeleteModel.get(key) is not None

    instance.delete()

    assert DeleteModel.get(key) is None

    unsaved_instance = DeleteModel(name="No Key")
    with pytest.raises(ValueError):
        unsaved_instance.delete()


def test_get_multi(reset_datastore):
    """Ensure get_multi retrieves instances and preserves order, including missing ones."""

    class BatchGetModel(Model):
        val = IntegerProperty()

    instances = [BatchGetModel(id=1, val=10), BatchGetModel(id=2, val=20), BatchGetModel(id=3, val=30)]
    keys = BatchGetModel.put_multi(instances)

    fetch_keys = [keys[2], keys[0], keys[1]]
    results: list[BatchGetModel] = BatchGetModel.get_multi(fetch_keys)

    assert len(results) == 3
    assert results[0].val == 30
    assert results[1].val == 10
    assert results[2].val == 20

    missing_key = BatchGetModel.key_from_id(999)
    mixed_keys = [keys[0], missing_key, keys[1]]
    mixed_results: list[BatchGetModel] = BatchGetModel.get_multi(mixed_keys)

    assert len(mixed_results) == 3
    assert mixed_results[0].val == 10
    assert mixed_results[1] is None
    assert mixed_results[2].val == 20

    assert BatchGetModel.get_multi([]) == []


def test_put_multi(reset_datastore):
    """Ensure put_multi saves multiple instances and generates auto-IDs."""

    class BatchPutModel(Model):
        val = IntegerProperty()

    instances = [BatchPutModel(id=101, val=10), BatchPutModel(id=102, val=20), BatchPutModel(val=30)]

    keys = BatchPutModel.put_multi(instances)

    assert len(keys) == 3
    assert keys[0].id == 101
    assert keys[1].id == 102
    assert keys[2].id is not None

    assert instances[2].key == keys[2]

    fetched_1 = BatchPutModel.get(keys[0])
    fetched_3 = BatchPutModel.get(keys[2])

    assert fetched_1.val == 10
    assert fetched_3.val == 30

    assert BatchPutModel.put_multi([]) == []


def test_delete_multi(reset_datastore):
    """Ensure delete_multi removes multiple instances from the emulator."""

    class BatchDelModel(Model):
        val = IntegerProperty()

    instances = [BatchDelModel(val=1), BatchDelModel(val=2), BatchDelModel(val=3)]
    keys = BatchDelModel.put_multi(instances)

    assert BatchDelModel.get(keys[0]) is not None
    assert BatchDelModel.get(keys[2]) is not None

    BatchDelModel.delete_multi(keys)

    assert BatchDelModel.get(keys[0]) is None
    assert BatchDelModel.get(keys[1]) is None
    assert BatchDelModel.get(keys[2]) is None

    BatchDelModel.delete_multi([])


def test_allocate_ids():
    """Ensure allocate_ids successfully reserves a batch of numeric IDs from Datastore."""

    class AllocModel(Model):
        pass

    keys = AllocModel.allocate_ids(size=5)

    assert len(keys) == 5
    for key in keys:
        assert isinstance(key, datastore.Key)
        assert key.is_partial is False
        assert isinstance(key.id, int)
        assert key.kind == "AllocModel"

    client = get_client()
    parent_key = client.key("ParentKind", "parent-1")
    child_keys = AllocModel.allocate_ids(size=2, parent=parent_key)

    assert len(child_keys) == 2
    assert child_keys[0].parent == parent_key

    with pytest.raises(ValueError, match="Number of IDs to allocate must be greater than 0"):
        AllocModel.allocate_ids(size=0)


def test_allocate_key_instance():
    """Ensure allocate_key assigns a real database ID to an instance."""

    class AllocInstModel(Model):
        pass

    m = AllocInstModel()
    assert m.key is None

    allocated_key = m.allocate_key()

    assert allocated_key is not None
    assert allocated_key == m.key
    assert m.key is not None
    assert m.key.is_partial is False
    assert isinstance(m.key.id, int)


def test_ensure_key_no_rpc():
    """Ensure _ensure_key assigns an incomplete key without needing the emulator."""

    class EnsureModel(Model):
        pass

    m = EnsureModel()
    assert m.key is None

    m._ensure_key()

    assert m.key is not None
    assert m.key.is_partial is True
    assert m.key.kind == "EnsureModel"

    original_key = m.key
    m._ensure_key()
    assert m.key is original_key


def test_lifecycle_hooks(reset_datastore):
    """Ensure all lifecycle hooks fire in the correct order for single and batch operations."""

    class HookModel(Model):
        name = StringProperty()

        history = []

        def _pre_put_hook(self):
            self.history.append("pre_put")

        def _post_put_hook(self):
            self.history.append("post_put")

        @classmethod
        def _pre_get_hook(cls, entity_key):
            cls.history.append("pre_get")

        @classmethod
        def _post_get_hook(cls, entity_key, instance):
            assert instance is None or isinstance(instance, HookModel)
            cls.history.append("post_get")

        @classmethod
        def _pre_delete_hook(cls, entity_key):
            cls.history.append("pre_delete")

        @classmethod
        def _post_delete_hook(cls, entity_key):
            cls.history.append("post_delete")

    HookModel.history.clear()

    m = HookModel(name="Alice")
    key = m.put()
    assert HookModel.history == ["pre_put", "post_put"]

    HookModel.history.clear()
    fetched = HookModel.get(key)
    assert HookModel.history == ["pre_get", "post_get"]

    HookModel.history.clear()
    missing_key = HookModel.key_from_id(999)
    HookModel.get(missing_key)

    assert HookModel.history == ["pre_get", "post_get"]

    HookModel.history.clear()
    fetched.delete()
    assert HookModel.history == ["pre_delete", "post_delete"]

    HookModel.history.clear()
    m1 = HookModel(name="Bob")
    m2 = HookModel(name="Charlie")
    keys = HookModel.put_multi([m1, m2])
    assert HookModel.history == ["pre_put", "pre_put", "post_put", "post_put"]

    HookModel.history.clear()
    HookModel.get_multi(keys)
    assert HookModel.history == ["pre_get", "pre_get", "post_get", "post_get"]

    HookModel.history.clear()
    HookModel.delete_multi(keys)
    assert HookModel.history == ["pre_delete", "pre_delete", "post_delete", "post_delete"]


def test_multi_tenant_routing_coverage():
    """Cover all namespace and project routing branches in Model and Query."""

    class TenantModel(Model):
        class Meta:
            kind = "Tenant"
            project = "custom-project"
            namespace = "custom-namespace"
            database = "custom-database"

    instance = TenantModel()
    instance.allocate_key()

    assert instance.key.project == "custom-project"
    assert instance.key.database == "custom-database"
    assert instance.key.namespace == "custom-namespace"

    repr_str = repr(instance)
    assert "project='custom-project'" in repr_str
    assert "database='custom-database'" in repr_str
    assert "namespace='custom-namespace'" in repr_str

    keys = TenantModel.allocate_ids(1)
    assert keys[0].project == "custom-project"
    assert keys[0].database == "custom-database"
    assert keys[0].namespace == "custom-namespace"

    key = TenantModel.key_from_id("test-id")
    assert key.project == "custom-project"
    assert key.database == "custom-database"
    assert key.namespace == "custom-namespace"

    q = TenantModel.query()
    list(q.fetch(limit=1))

    class BasicModel(Model):
        pass

    adhoc_inst = BasicModel(project="p2", namespace="n2")
    assert adhoc_inst.key.project == "p2"

    adhoc_key = BasicModel.key_from_id("id", project="p3", namespace="n3")
    assert adhoc_key.project == "p3"

    adhoc_alloc = BasicModel.allocate_ids(1, project="p4", namespace="n4")[0]
    assert adhoc_alloc.project == "p4"

    adhoc_query = BasicModel.query(project="p5", namespace="n5")
    list(adhoc_query.fetch(limit=1))


def test_multi_batch_project_mismatch():
    """Ensure batch operations fail fast if instances belong to different projects."""

    class BatchModel(Model):
        pass

    k1 = BatchModel.client(project="p1").key(BatchModel.kind(), 1)
    k2 = BatchModel.client(project="p2").key(BatchModel.kind(), 2)
    with pytest.raises(ValueError):
        BatchModel.get_multi([k1, k2])

    with pytest.raises(ValueError):
        BatchModel.delete_multi([k1, k2])

    inst1 = BatchModel(project="p1")
    inst2 = BatchModel(project="p2")
    with pytest.raises(ValueError):
        BatchModel.put_multi([inst1, inst2])


def test_ensure_key_with_meta_namespace():
    """Cover the namespace injection branch inside _ensure_key."""

    class MetaNamespaceModel(Model):
        class Meta:
            kind = "EnsuredKind"
            namespace = "test-namespace"

    instance = MetaNamespaceModel()
    assert instance.key is None

    # noinspection PyProtectedMember
    instance._ensure_key()
    assert instance.key is not None
    assert instance.key.namespace == "test-namespace"


def test_put_projected_entity_raises_error():
    """Ensure calling put() on a projected entity raises a RuntimeError to prevent data loss."""

    class ProjectedModel(Model):
        name = StringProperty()
        age = IntegerProperty()

    instance = ProjectedModel(name="Alice", _is_projected=True)

    with pytest.raises(RuntimeError, match="Cannot save an entity fetched via a Projection query"):
        instance.put()


def test_put_multi_projected_entity_raises_error():
    """Ensure calling put_multi() with any projected entity raises a RuntimeError."""

    class ProjectedModel(Model):
        name = StringProperty()
        age = IntegerProperty()

    normal_instance = ProjectedModel(name="Bob", age=30)
    projected_instance = ProjectedModel(name="Alice", _is_projected=True)

    with pytest.raises(RuntimeError, match="Cannot save an entity fetched via a Projection query"):
        ProjectedModel.put_multi([normal_instance, projected_instance])


def test_model_put_repeated_property_serialization():
    """Verify put() correctly maps serialization hooks over repeated arrays."""

    class ArrayModel(Model):
        dates = DateProperty(repeated=True)

    instance = ArrayModel(dates=[datetime.date(2025, 1, 1), datetime.date(2025, 1, 2)])
    instance_key = instance.put()

    saved_entity = ArrayModel.get_by_id(instance_key.id_or_name)

    assert isinstance(saved_entity["dates"][0], datetime.date)
    assert isinstance(saved_entity["dates"][1], datetime.date)


def test_model_put_multi_repeated_property_serialization():
    """Verify put_multi() correctly maps serialization hooks over repeated arrays."""

    class ArrayModel(Model):
        dates = DateProperty(repeated=True)

    instances = [ArrayModel(dates=[datetime.date(2025, 1, 1)])]
    instances_keys = ArrayModel.put_multi(instances)

    saved_entities = ArrayModel.get_multi(instances_keys)

    assert isinstance(saved_entities[0]["dates"][0], datetime.date)


def test_model_from_entity_repeated_property_hydration():
    """Verify from_entity() correctly maps hydration hooks over repeated arrays."""

    class ArrayModel(Model):
        dates: list = DateProperty(repeated=True)

    ds_entity = datastore.Entity()
    ds_entity.update(
        {
            "dates": [
                datetime.datetime(2025, 1, 1, tzinfo=datetime.timezone.utc),
                datetime.datetime(2025, 1, 2, tzinfo=datetime.timezone.utc),
            ]
        }
    )

    instance = ArrayModel.from_entity(ds_entity)

    assert isinstance(instance.dates[0], datetime.date)
    assert isinstance(instance.dates[1], datetime.date)


def test_model_from_entity_safe_key_missing():
    """Verify from_entity safely handles EmbeddedEntities / dicts that lack a key attribute."""

    class SimpleModel(Model):
        name = StringProperty()

    class EmbeddedEntityStub(dict):
        pass

    stub = EmbeddedEntityStub({"name": "Alice"})

    assert not hasattr(stub, "key")

    instance = SimpleModel.from_entity(stub)

    assert instance.name == "Alice"
    assert instance.key is None
