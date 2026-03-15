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
    - Datastore aliasing (name)
    - Indexing control (indexed)
    - List support (repeated)
    - Value restriction (choices)
    """

    def __init__(
            self,
            *,
            name: Optional[str] = None,
            indexed: bool = True,
            repeated: bool = False,
            required: bool = False,
            default: Any = None,
            choices: Optional[list] = None,
            validators: Optional[List[Callable]] = None,
    ):
        self._datastore_name = name
        self.indexed = indexed
        self.repeated = repeated
        self.required = required
        self.choices = choices
        self.validators: List[Callable] = validators or []

        # NDB Standard: repeated properties default to an empty list
        if self.repeated and default is None:
            self.default = []
        else:
            self.default = default

        # Ensure all validators are callable
        for validator in self.validators:
            if not callable(validator):
                raise TypeError(f"Validator {validator} for property '{self}' is not callable")

    def __set_name__(self, owner, name: str):
        """Called by Python to set the attribute name on the owner class."""
        self._python_name = name
        if not self._datastore_name:
            self._datastore_name = name

    def _validate_type(self, value: Any) -> Any:
        """Override in subclasses to enforce Python types."""
        return value

    def _validate_single_value(self, instance: "Model", value: Any) -> Any:
        """Validates a single item (used directly, or mapped over a list if repeated=True)"""
        # 1. Enforce type
        value = self._validate_type(value)

        # 2. Enforce choices
        if self.choices is not None and value not in self.choices:
            raise ValueError(f"Value '{value}' must be one of {self.choices}")

        # 3. Apply property-level validators (inline)
        for validator in self.validators:
            value = validator(value)

        # 4. Apply field validators (model methods)
        field_validator_methods = getattr(instance, "_field_validators", {}).get(self._python_name, [])
        for method_name in field_validator_methods:
            method = getattr(instance, method_name)
            value = method(value)

        return value

    def validate(self, instance: "Model", value: Any) -> Any:
        """
        Validate and process a value for this property.
        """
        # 1. Check required
        if value is None:
            if self.required:
                raise ValueError(f"Property '{self._python_name}' is required")
            return [] if self.repeated else None

        # 2. Handle Repeated (List) vs Single Value
        if self.repeated:
            if not isinstance(value, (list, tuple, set)):
                raise TypeError(f"Property '{self._python_name}' is repeated and requires an iterable")

            if self.required and len(value) == 0:
                raise ValueError(f"Property '{self._python_name}' is required and cannot be empty")

            validated_list = []
            for item in value:
                if item is None:
                    raise ValueError(f"Repeated property '{self._python_name}' cannot contain None items")
                validated_list.append(self._validate_single_value(instance, item))
            return validated_list
        else:
            return self._validate_single_value(instance, value)

    # --------------------
    # Descriptor protocol
    # --------------------

    def __get__(self, instance: Optional["Model"], owner):
        if instance is None:
            return self
        # noinspection PyProtectedMember
        return instance._values.get(self._python_name, self.default)

    def __set__(self, instance: "Model", value):
        # noinspection PyProtectedMember
        instance._values[self._python_name] = self.validate(instance, value)

    def __delete__(self, instance: "Model"):
        # noinspection PyProtectedMember
        instance._values.pop(self._python_name, None)


class StringProperty(Property):
    def _validate_type(self, value: Any) -> Any:
        if not isinstance(value, str):
            raise TypeError(f"Property '{self._python_name}' must be str")
        return value


class IntegerProperty(Property):
    def _validate_type(self, value: Any) -> Any:
        if not isinstance(value, int) or isinstance(value, bool):
            raise TypeError(f"Property '{self._python_name}' must be int")
        return value
