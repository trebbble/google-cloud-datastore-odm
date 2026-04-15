import datetime

import pytest
from google.cloud import datastore

from src.google_cloud_datastore_odm.model import Model, field_validator
from src.google_cloud_datastore_odm.properties import (
    BooleanProperty,
    DateProperty,
    DateTimeProperty,
    FloatProperty,
    IntegerProperty,
    JsonProperty,
    Property,
    StringProperty,
    TextProperty,
    TimeProperty,
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
    prop = TextModel._properties['body']

    assert prop._to_base_type("normal string") == "normal string"
    assert prop._from_base_type("normal string") == "normal string"

    with pytest.raises(TypeError):
        instance.body = 123

    with pytest.raises(TypeError):
        prop._to_base_type(123)

    with pytest.raises(ValueError):
        class BadTextModel(Model):
            body = TextProperty(indexed=True)

    class CompressedTextModel(Model):
        body = TextProperty(compressed=True)

    prop = CompressedTextModel._properties['body']

    datastore_value = prop._to_base_type("Compress me please")
    assert isinstance(datastore_value, bytes)

    python_value = prop._from_base_type(datastore_value)
    assert python_value == "Compress me please"


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

    with pytest.raises(ValueError):
        class BadJsonModel(Model):
            data = JsonProperty(indexed=True)

    class CompressedJsonModel(Model):
        data = JsonProperty(compressed=True)

    prop = CompressedJsonModel._properties['data']
    test_payload = {"deep": {"nested": "value"}}

    datastore_value = prop._to_base_type(test_payload)
    assert isinstance(datastore_value, bytes)

    python_value = prop._from_base_type(datastore_value)
    assert python_value == test_payload

    assert prop._to_base_type(None) is None

    prop = JsonModel._properties['data']
    assert prop._to_base_type({"key": "value"}) == {"key": "value"}

    class UnserializableObject:
        pass

    with pytest.raises(TypeError, match="must be JSON serializable"):
        prop._to_base_type(UnserializableObject())


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

    instance = RequiredModel()

    with pytest.raises(ValueError):
        instance.put()


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

    instance = RepeatedModel()
    assert instance.tags == []

    with pytest.raises(ValueError):
        instance.put()

    instance.tags = ["python", "odm"]
    assert instance.tags == ["python", "odm"]

    with pytest.raises(TypeError):
        instance.tags = "not_a_list"

    with pytest.raises(TypeError):
        instance.tags = ["valid", 123]

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
        text = StringProperty()

        class Meta:
            kind = "Dummy"

    instance = DummyModel.from_entity(None)
    assert instance is None


def test_default_non_accessible_if_projection():
    class DummyModel(Model):
        text = StringProperty(default="hello there")

    instance = DummyModel(_is_projected=True)

    with pytest.raises(AttributeError):
        _ = instance.text


def test_datetime_auto_now_add():
    class TimeModel(Model):
        created_at = DateTimeProperty(auto_now_add=True)
        updated_at = DateTimeProperty(auto_now=True)
        time_auto = TimeProperty(auto_now=True)

    instance = TimeModel()

    TimeModel._properties['created_at']._prepare_for_put(instance)
    TimeModel._properties['updated_at']._prepare_for_put(instance)
    TimeModel._properties['time_auto']._prepare_for_put(instance)

    assert isinstance(instance.created_at, datetime.datetime)
    assert isinstance(instance.updated_at, datetime.datetime)
    assert isinstance(instance.time_auto, datetime.time)


def test_date_and_time_property_casting():
    class SchedModel(Model):
        day = DateProperty()
        hour = TimeProperty()

    instance = SchedModel()
    instance.day = datetime.date(2025, 1, 1)
    instance.hour = datetime.time(14, 30)

    with pytest.raises(TypeError):
        instance.day = datetime.datetime.now()

    # noinspection PyProtectedMember
    ds_day = SchedModel._properties['day']._to_base_type(instance.day)
    assert isinstance(ds_day, datetime.datetime)
    assert ds_day.year == 2025

    # noinspection PyProtectedMember
    py_day = SchedModel._properties['day']._from_base_type(ds_day)
    assert isinstance(py_day, datetime.date)

    # noinspection PyProtectedMember
    ds_hour = SchedModel._properties['hour']._to_base_type(instance.hour)
    assert isinstance(ds_hour, datetime.datetime)
    assert ds_hour.year == 1970
    assert ds_hour.hour == 14

    # noinspection PyProtectedMember
    py_hour = SchedModel._properties['hour']._from_base_type(ds_hour)
    assert isinstance(py_hour, datetime.time)

    # --- None Casts (Covering the early exit branches) ---
    # noinspection PyProtectedMember
    assert SchedModel._properties['day']._to_base_type(None) is None
    # noinspection PyProtectedMember
    assert SchedModel._properties['day']._from_base_type(None) is None
    # noinspection PyProtectedMember
    assert SchedModel._properties['hour']._to_base_type(None) is None
    # noinspection PyProtectedMember
    assert SchedModel._properties['hour']._from_base_type(None) is None


def test_datetime_hydration_conversions():
    """Test naive/aware timezone conversions during Datastore hydration."""

    class TzModel(Model):
        dt_aware = DateTimeProperty(tzinfo=datetime.timezone.utc)
        dt_naive = DateTimeProperty()
        d = DateProperty()
        t = TimeProperty()

    ds_entity = datastore.Entity()

    utc_now = datetime.datetime(2025, 1, 1, 12, 0, tzinfo=datetime.timezone.utc)

    ds_entity.update({
        "dt_aware": datetime.datetime(2025, 1, 1, 12, 0),
        "dt_naive": utc_now,
        "d": utc_now,
        "t": utc_now,
    })

    instance = TzModel.from_entity(ds_entity)

    assert instance.dt_aware.tzinfo == datetime.timezone.utc
    assert instance.dt_naive.tzinfo is None
    assert isinstance(instance.d, datetime.date)
    assert isinstance(instance.t, datetime.time)


def test_datetime_and_time_edge_cases_via_model():
    """Test Datetime/Date/Time edge cases using high-level model API."""

    with pytest.raises(ValueError):
        class BadModel(Model):
            dt = DateTimeProperty(repeated=True, auto_now=True)

    class ChronoModel(Model):
        dt_naive = DateTimeProperty()
        dt_aware = DateTimeProperty(tzinfo=datetime.timezone.utc)
        d = DateProperty()
        t = TimeProperty()

    instance = ChronoModel()

    with pytest.raises(TypeError):
        instance.dt_naive = "not a datetime"

    with pytest.raises(TypeError):
        instance.d = datetime.datetime.now()

    with pytest.raises(TypeError):
        instance.t = datetime.datetime.now()

    with pytest.raises(ValueError):
        instance.dt_naive = datetime.datetime.now(datetime.timezone.utc)

    # noinspection PyProtectedMember
    assert ChronoModel._properties['dt_naive']._from_base_type(None) is None

    class BypassModel(Model):
        created_at = DateProperty(auto_now_add=True)
        time_at = TimeProperty(auto_now_add=True)

    explicit_date = datetime.date(2020, 1, 1)
    explicit_time = datetime.time(12, 0)
    bypass_instance = BypassModel(created_at=explicit_date, time_at=explicit_time)

    for prop in BypassModel._properties.values():
        # noinspection PyProtectedMember
        prop._prepare_for_put(bypass_instance)

    assert bypass_instance.created_at == explicit_date
    assert bypass_instance.time_at == explicit_time


def test_datetime_naive_to_naive_pass_through():
    """Cover the final 'return value' branch in DateTimeProperty._from_base_type."""

    class NaiveModel(Model):
        dt = DateTimeProperty()  # tzinfo is None

    # Simulate Datastore (or a mock) returning a naive datetime
    naive_val = datetime.datetime(2025, 1, 1, 12, 0)

    # noinspection PyProtectedMember
    result = NaiveModel._properties['dt']._from_base_type(naive_val)

    # It should pass straight through untouched
    assert result.tzinfo is None
    assert result == naive_val


def test_date_and_time_auto_now_add_triggers():
    """Cover the setattr execution in DateProperty and TimeProperty _prepare_for_put."""

    class AutoModel(Model):
        d = DateProperty(auto_now_add=True)
        t = TimeProperty(auto_now_add=True)

    instance = AutoModel()

    for prop in AutoModel._properties.values():
        # noinspection PyProtectedMember
        prop._prepare_for_put(instance)

    assert isinstance(instance.d, datetime.date)
    assert isinstance(instance.t, datetime.time)
