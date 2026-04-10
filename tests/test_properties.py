import pytest
from google.cloud import datastore

from src.google_cloud_datastore_odm.model import Model, field_validator
from src.google_cloud_datastore_odm.properties import (
    BooleanProperty,
    FloatProperty,
    IntegerProperty,
    JsonProperty,
    Property,
    StringProperty,
    TextProperty,
)


def reject_trigger_value(value):
    if value == 'trigger_error':
        raise ValueError("Triggered error")
    return value


class DemoModel(Model):
    text_field = StringProperty()
    number_field = IntegerProperty()
    custom_validated = StringProperty(validators=[reject_trigger_value])

    @field_validator('text_field')
    def validate_text_field_length(self, value: str) -> str:
        if len(value) < 2 or len(value) > 5:
            raise ValueError("Text characters length should be [2-5].")
        return value

    @field_validator('text_field')
    def validate_text_field_choices(self, value: str) -> str:
        if value not in ["hi", "hey"]:
            raise ValueError("Text characters should be [hi,hey].")

        return value

    @field_validator('number_field')
    def validate_number_field(self, value: int) -> int:
        if value < 1 or value > 10:
            raise ValueError("Number should be in [1-10].")

        if value not in [1, 5, 10]:
            raise ValueError("Number should be one of [1, 5, 10].")
        return value


def test_string_field_validation():
    instance = DemoModel(text_field="hi", number_field=5)
    assert instance.text_field == "hi"

    with pytest.raises(ValueError):
        instance.text_field = "h"

    with pytest.raises(ValueError):
        instance.text_field = "hello!"

    with pytest.raises(ValueError):
        instance.text_field = "yo"

    assert instance.text_field == "hi"
    instance.text_field = "hey"
    assert instance.text_field == "hey"


def test_string_field_custom_validation():
    instance = DemoModel(text_field="hi", number_field=5)
    assert instance.custom_validated is None

    with pytest.raises(ValueError):
        instance.custom_validated = "trigger_error"

    assert instance.custom_validated is None
    instance.custom_validated = "test"
    assert instance.custom_validated == "test"


def test_integer_field_validation():
    instance = DemoModel(text_field="hi", number_field=1)
    assert instance.number_field == 1

    with pytest.raises(ValueError):
        instance.number_field = 0

    with pytest.raises(ValueError):
        instance.number_field = 15

    with pytest.raises(ValueError):
        instance.number_field = 3

    assert instance.number_field == 1
    instance.number_field = 5
    assert instance.number_field == 5


def test_field_invalid_validator():
    with pytest.raises(TypeError):
        StringProperty(validators=["not_a_function"])


def test_field_type_enforcement():
    class TypeTestModel(Model):
        text = StringProperty()
        integer = IntegerProperty()

    instance = TypeTestModel()

    with pytest.raises(TypeError):
        instance.text = 123

    with pytest.raises(TypeError):
        instance.integer = 'test'

    with pytest.raises(TypeError):
        instance.integer = True

    instance.text = "valid"
    assert instance.text == "valid"


def test_boolean_property():
    class BoolModel(Model):
        is_active = BooleanProperty()

    instance = BoolModel()

    instance.is_active = True
    assert instance.is_active is True
    instance.is_active = False
    assert instance.is_active is False

    with pytest.raises(TypeError):
        instance.is_active = 1

    with pytest.raises(TypeError):
        instance.is_active = "True"


def test_float_property():
    class FloatModel(Model):
        score = FloatProperty()

    instance = FloatModel()

    instance.score = 99.5
    assert instance.score == 99.5

    instance.score = 100
    assert instance.score == 100.0
    assert isinstance(instance.score, float)

    with pytest.raises(TypeError):
        instance.score = "99.5"

    with pytest.raises(TypeError):
        instance.score = True


def test_text_property():
    class TextModel(Model):
        body = TextProperty()

    assert TextModel.body.indexed is False

    instance = TextModel()
    instance.body = "A very long text block..."
    assert instance.body == "A very long text block..."

    with pytest.raises(TypeError):
        instance.body = 123


def test_json_property():
    class JsonModel(Model):
        data = JsonProperty()

    assert JsonModel.data.indexed is False

    instance = JsonModel()

    instance.data = {"key": "value", "list": [1, 2, 3]}
    assert instance.data == {"key": "value", "list": [1, 2, 3]}

    instance.data = [1, "two", 3.0]
    assert instance.data == [1, "two", 3.0]

    with pytest.raises(TypeError):
        instance.data = {"key": {1, 2, 3}}

    class CustomObj:
        pass

    with pytest.raises(TypeError):
        instance.data = CustomObj()


def test_field_descriptor_delete():
    class DeleteTestModel(Model):
        text = StringProperty()

    instance = DeleteTestModel(text="initial")
    assert instance.text == "initial"

    del instance.text
    assert instance.text is None


def test_field_descriptor_get_on_class():
    class ClassPropModel(Model):
        text = StringProperty()

    assert isinstance(ClassPropModel.text, StringProperty)


def test_field_required_none_value():
    class RequiredModel(Model):
        text = StringProperty(required=True)

    instance = RequiredModel(text="valid")

    with pytest.raises(ValueError):
        instance.text = None


def test_field_optional_none_value():
    class OptionalModel(Model):
        text = StringProperty(required=False)

    instance = OptionalModel(text=None)
    assert instance.text is None


def test_metaclass_rejects_non_callable_field_validator():
    with pytest.raises(TypeError):
        class MockValidator:
            pass

        bad_mock = MockValidator()
        bad_mock.__field_validator__ = 'text'

        class BadModel(Model):
            text = StringProperty()
            bad_validator = bad_mock


def test_base_property_validate_type():
    class BasePropModel(Model):
        untyped_field = Property()

    instance = BasePropModel(untyped_field={"complex": "object"})
    assert instance.untyped_field == {"complex": "object"}


def test_repeated_property():
    class RepeatedModel(Model):
        tags = StringProperty(repeated=True)
        req_tags = StringProperty(repeated=True, required=True)

    instance = RepeatedModel(req_tags=["init"])
    assert instance.tags == []

    instance.tags = ["python", "odm"]
    assert instance.tags == ["python", "odm"]

    with pytest.raises(TypeError):
        instance.tags = "not_a_list"

    with pytest.raises(TypeError):
        instance.tags = ["valid", 123]

    with pytest.raises(ValueError):
        instance.req_tags = []

    with pytest.raises(ValueError):
        instance.tags = ["valid", None]

    instance.tags = None
    assert instance.tags == []


def test_property_choices_violation():
    class ChoiceModel(Model):
        status = StringProperty(choices=["draft", "published"])

    instance = ChoiceModel(status="draft")

    with pytest.raises(ValueError):
        instance.status = "archived"


def test_json_property_from_base_type_scrubs_entities():
    """Verify that JsonProperty correctly scrubs <Entity> wrappers during hydration."""

    class JsonModel(Model):
        __kind__ = "JsonModel"
        data: dict | list = JsonProperty()

    ds_entity = datastore.Entity()
    nested_entity = datastore.Entity()

    nested_entity.update({"inner_key": "inner_value"})
    ds_entity.update({"data": {"nested": nested_entity, "list": [1, 2]}})

    instance = JsonModel.from_entity(ds_entity)

    assert isinstance(instance.data["nested"], dict)
    assert not isinstance(instance.data["nested"], datastore.Entity)
    assert instance.data == {
        "nested": {"inner_key": "inner_value"},
        "list": [1, 2]
    }


def test_json_property_from_base_type_handles_none():
    """Verify that the hook handles None safely."""
    prop = JsonProperty()
    # noinspection PyProtectedMember
    assert prop._from_base_type(None) is None


def test_model_from_entity_with_none():
    """Cover the early-exit None check in Model.from_entity."""

    class DummyModel(Model):
        __kind__ = "Dummy"
        text = StringProperty()

    instance = DummyModel.from_entity(None)
    assert instance is None
