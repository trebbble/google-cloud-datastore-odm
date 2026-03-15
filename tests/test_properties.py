import pytest

from src.google_cloud_datastore_odm.model import Model, field_validator
from src.google_cloud_datastore_odm.properties import IntegerProperty, Property, StringProperty


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

    instance.text = "valid"
    assert instance.text == "valid"


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

    with pytest.raises(ValueError, match="must be one of"):
        instance.status = "archived"
