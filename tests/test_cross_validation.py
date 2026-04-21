import pytest

from google_cloud_datastore_odm.model import Model, field_validator, model_validator
from google_cloud_datastore_odm.properties import IntegerProperty, StringProperty


def append_suffix_inline(value: str) -> str:
    """Inline property validator."""
    return value + "_inline"


class OrderVerificationModel(Model):
    """
    Model designed to test the exact execution order:
    1. Python Type Check (StringProperty)
    2. Inline Validator (append_suffix_inline)
    3. Field Validator (append_suffix_field)
    4. Model Validator (validate_final_state)
    """

    chain_field = StringProperty(validators=[append_suffix_inline])
    amount = IntegerProperty()

    @field_validator("chain_field")
    def append_suffix_field(self, value: str) -> str:
        return value + "_field"

    @model_validator
    def validate_final_state(self):
        if self.chain_field == "base_inline_field" and self.amount == 0:
            raise ValueError("Amount cannot be zero when chain_field is fully built.")


def test_property_validation_execution_order():
    """Ensures type -> inline -> field validators run sequentially upon assignment."""
    instance = OrderVerificationModel()

    instance.chain_field = "base"
    assert instance.chain_field == "base_inline_field"


def test_model_validation_boundary():
    """Ensures model validators do NOT run on property assignment, only on .validate()."""

    instance = OrderVerificationModel(chain_field="base", amount=0)

    assert instance.chain_field == "base_inline_field"
    assert instance.amount == 0

    with pytest.raises(ValueError):
        instance.validate()


def test_put_triggers_model_validation():
    """Ensures .put() triggers the model validators before writing."""
    instance = OrderVerificationModel(chain_field="base", amount=0)

    with pytest.raises(ValueError):
        instance.put()


def test_inherited_validators():
    """
    Covers metaclass inheritance for both _field_validators and _model_validators.
    Ensures both are properly merged and executed on the child instance.
    """

    class ParentModel(Model):
        shared_text = StringProperty()
        parent_count = IntegerProperty(default=0)

        @field_validator("shared_text")
        def validate_shared_text(self, value: str) -> str:
            if value == "bad_parent_value":
                raise ValueError("Blocked by parent field validator")
            return value

        @model_validator
        def validate_parent_state(self):
            if self.shared_text == "invalid_state" and self.parent_count > 5:
                raise ValueError("Blocked by parent model validator")

    class ChildModel(ParentModel):
        child_text = StringProperty()

        @model_validator
        def validate_child_state(self):
            if self.child_text == "bad_child":
                raise ValueError("Blocked by child model validator")

    assert "shared_text" in ChildModel._field_validators
    assert "validate_shared_text" in ChildModel._field_validators["shared_text"]

    assert len(ChildModel._model_validators) == 2
    validator_names = [v.__name__ for v in ChildModel._model_validators]
    assert "validate_parent_state" in validator_names
    assert "validate_child_state" in validator_names

    instance = ChildModel(shared_text="ok", child_text="ok", parent_count=0)
    instance.validate()

    with pytest.raises(ValueError):
        instance.shared_text = "bad_parent_value"

    instance.shared_text = "invalid_state"
    instance.parent_count = 10
    with pytest.raises(ValueError):
        instance.validate()

    instance.shared_text = "ok"
    instance.child_text = "bad_child"
    with pytest.raises(ValueError):
        instance.validate()
