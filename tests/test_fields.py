import pytest
from src.google_cloud_datastore_odm.fields import StringField, IntegerField
from src.google_cloud_datastore_odm.model import Model


def reject_trigger_value(value):
    if value == 'trigger_error':
        raise ValueError
    return value


class DemoModel(Model):
    text_field = StringField(
        min_length=2,
        max_length=5,
        choices=["hi", "hey"],
    )
    number_field = IntegerField(
        min_value=1,
        max_value=10,
        choices=[1, 5, 10],
    )
    custom_validated = StringField(validators=[reject_trigger_value])


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
    with pytest.raises(TypeError, match="is not callable"):
        StringField(validators=["not_a_function"])


def test_field_type_enforcement():
    class TypeTestModel(Model):
        text = StringField()

    instance = TypeTestModel()
    
    with pytest.raises(TypeError, match="must be str"):
        instance.text = 123
        
    instance.text = "valid"
    assert instance.text == "valid"


def test_field_descriptor_delete():
    class DeleteTestModel(Model):
        text = StringField()

    instance = DeleteTestModel(text="initial")
    assert instance.text == "initial"
    
    del instance.text
    assert instance.text is None


def test_field_descriptor_get_on_class():
    class ClassPropModel(Model):
        text = StringField()

    assert isinstance(ClassPropModel.text, StringField)


def test_field_required_none_value():
    class RequiredModel(Model):
        text = StringField(required=True)
        
    instance = RequiredModel(text="valid")
    
    with pytest.raises(ValueError, match="is required"):
        instance.text = None


def test_field_optional_none_value():
    class OptionalModel(Model):
        text = StringField(required=False)
        
    instance = OptionalModel()
    assert instance.text is None
