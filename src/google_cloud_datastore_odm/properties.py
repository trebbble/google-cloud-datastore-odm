from typing import TYPE_CHECKING, Any, Callable, List, Optional

if TYPE_CHECKING:
    from .model import Model  # Only for static analysis, avoids circular import


class Property:
    """
    Base descriptor for model properties.

    Responsibilities:
    - Required checks
    - Python type enforcement
    - Property-level validators
    - Model-level field validators
    """

    def __init__(
        self,
        *,
        required: bool = False,
        default: Any = None,
        validators: Optional[List[Callable]] = None,
    ):
        self.name: Optional[str] = None
        self.required = required
        self.default = default
        self.validators: List[Callable] = validators or []
        # Ensure all validators are callable
        for validator in self.validators:
            if not callable(validator):
                raise TypeError(f"Validator {validator} for property '{self}' is not callable")

    def __set_name__(self, owner, name: str):
        """Called by Python to set the attribute name on the owner class."""
        self.name = name

    def _validate_type(self, value: Any) -> Any:
        """Override in subclasses to enforce Python types."""
        return value

    def validate(self, instance: "Model", value: Any) -> Any:
        """
        Validate and process a value for this property.

        Steps:
        1. Check required
        2. Enforce type
        3. Apply property-level validators (inline)
        4. Apply field validators (model methods)
        """
        if value is None:
            if self.required:
                raise ValueError(f"Property '{self.name}' is required")
            return None

        value = self._validate_type(value)

        for validator in self.validators:
            value = validator(value)

        field_validator_methods = getattr(instance, "_field_validators", {}).get(self.name, [])
        for method_name in field_validator_methods:
            method = getattr(instance, method_name)
            value = method(value)

        return value

    # --------------------
    # Descriptor protocol
    # --------------------

    def __get__(self, instance: Optional["Model"], owner):
        if instance is None:
            return self
        # noinspection PyProtectedMember
        return instance._values.get(self.name, self.default)

    def __set__(self, instance: "Model", value):
        # noinspection PyProtectedMember
        instance._values[self.name] = self.validate(instance, value)

    def __delete__(self, instance: "Model"):
        # noinspection PyProtectedMember
        instance._values.pop(self.name, None)


class StringProperty(Property):
    def _validate_type(self, value: Any) -> Any:
        if not isinstance(value, str):
            raise TypeError(f"Property '{self.name}' must be str")
        return value


class IntegerProperty(Property):
    def _validate_type(self, value: Any) -> Any:
        if not isinstance(value, int):
            raise TypeError(f"Property '{self.name}' must be int")
        return value
