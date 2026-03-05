from typing import TYPE_CHECKING, Any, Callable, List, Optional

if TYPE_CHECKING:
    from .model import Model  # Only for static analysis, avoids circular import


class Field:
    """
    Base descriptor for model fields.

    Responsibilities:
    - Required checks
    - Python type enforcement
    - Field-level validators
    """

    python_type: Optional[type] = None

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
                raise TypeError(f"Validator {validator} for field '{self}' is not callable")

    def __set_name__(self, owner, name: str):
        """Called by Python to set the attribute name on the owner class."""
        self.name = name

    def validate(self, value: Any) -> Any:
        """
        Validate and process a value for this field.

        Steps:
        1. Check required
        2. Enforce type
        3. Apply field-level validators
        """
        if value is None:
            if self.required:
                raise ValueError(f"Field '{self.name}' is required")
            return None

        if self.python_type and not isinstance(value, self.python_type):
            raise TypeError(f"Field '{self.name}' must be {self.python_type.__name__}")

        # Field-level validators
        for validator in self.validators:
            value = validator(value)

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
        instance._values[self.name] = self.validate(value)

    def __delete__(self, instance: "Model"):
        # noinspection PyProtectedMember
        instance._values.pop(self.name, None)


class StringField(Field):
    python_type = str

    def __init__(
        self,
        *,
        min_length: Optional[int] = None,
        max_length: Optional[int] = None,
        choices: Optional[List[str]] = None,
        **kwargs,
    ):
        super().__init__(**kwargs)
        self.min_length = min_length
        self.max_length = max_length
        self.choices = choices

        if self.min_length is not None:
            self.validators.append(self._validate_min_length)
        if self.max_length is not None:
            self.validators.append(self._validate_max_length)
        if self.choices:
            self.validators.append(self._validate_choices)

    def _validate_min_length(self, value: str) -> str:
        if len(value) < self.min_length:
            raise ValueError(f"String must be at least {self.min_length} characters")
        return value

    def _validate_max_length(self, value: str) -> str:
        if len(value) > self.max_length:
            raise ValueError(f"String must be at most {self.max_length} characters")
        return value

    def _validate_choices(self, value: str) -> str:
        if value not in self.choices:
            raise ValueError(f"Value must be one of {self.choices}")
        return value


class IntegerField(Field):
    python_type = int

    def __init__(
        self,
        *,
        min_value: Optional[int] = None,
        max_value: Optional[int] = None,
        choices: Optional[List[int]] = None,
        **kwargs,
    ):
        super().__init__(**kwargs)
        self.min_value = min_value
        self.max_value = max_value
        self.choices = choices

        if self.min_value is not None:
            self.validators.append(self._validate_min_value)
        if self.max_value is not None:
            self.validators.append(self._validate_max_value)
        if self.choices:
            self.validators.append(self._validate_choices)

    def _validate_min_value(self, value: int) -> int:
        if value < self.min_value:
            raise ValueError(f"Value must be >= {self.min_value}")
        return value

    def _validate_max_value(self, value: int) -> int:
        if value > self.max_value:
            raise ValueError(f"Value must be <= {self.max_value}")
        return value

    def _validate_choices(self, value: int) -> int:
        if value not in self.choices:
            raise ValueError(f"Value must be one of {self.choices}")
        return value
