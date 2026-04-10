"""
Property descriptors for the Google Cloud Datastore ODM.

This module provides the base `Property` descriptor and its type-specific subclasses
(e.g., `StringProperty`, `IntegerProperty`). These classes handle data coercion,
validation, default values, and Datastore schema mapping.
"""

import datetime
import json
from typing import TYPE_CHECKING, Any, Callable, List, Optional

if TYPE_CHECKING:
    from .model import Model


class Property:
    """Base descriptor for model properties.

    This class implements the Python descriptor protocol (`__get__`, `__set__`, `__delete__`)
    to manage state on the underlying `Model` instances.

    Responsibilities:
    - Required checks and default value assignment
    - Python type enforcement (via subclasses)
    - Inline property-level validators
    - Routing to Model-level `@field_validator` methods
    - Datastore aliasing (`name`)
    - Indexing control (`indexed`)
    - List support (`repeated`)
    - Value restriction (`choices`)
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
        """Initialize a new Property.

        Args:
            name (Optional[str]): The Datastore column name. If omitted, defaults to
                the Python attribute name. Useful for mapping legacy database fields.
            indexed (bool): Whether the Datastore should index this property. Set to
                False for massive text blocks to save space and reduce write costs. If not sure leave this True
                and pass unindexed properties on the fly during put() operations.
            repeated (bool): If True, this property expects an iterable (list/set/tuple)
                and stores it as an array in Datastore. Defaults to False.
            required (bool): If True, assigning `None` or an empty list (if repeated)
                will raise a ValueError. Defaults to False.
            default (Any): The default value or a zero-argument callable to generate one
                (e.g., `default=list` or `default=datetime.now`).
            choices (Optional[list]): An optional list of allowed values. Assignments
                not in this list will raise a ValueError.
            validators (Optional[List[Callable]]): A list of custom validation functions.
                Each function should accept a single value, validate/mutate it, and return it.

        Raises:
            TypeError: If any provided validator is not callable.

        Example:
            ```python
            status = StringProperty(
                default="draft",
                choices=["draft", "published"],
                name="legacy_status_col"
            )
            tags = StringProperty(repeated=True)
            ```
        """
        self.datastore_name = name
        self.indexed = indexed
        self.repeated = repeated
        self.required = required
        self.choices = choices
        self.validators: List[Callable] = validators or []

        if self.repeated and default is None:
            self.default = []
        else:
            self.default = default

        for validator in self.validators:
            if not callable(validator):
                raise TypeError(f"Validator {validator} for property '{self}' is not callable")

    def __set_name__(self, owner: type, name: str) -> None:
        """Called automatically by Python to set the attribute name.

        Args:
            owner (type): The class that owns this descriptor.
            name (str): The name of the attribute on the class.
        """
        self._python_name = name
        if not self.datastore_name:
            self.datastore_name = name

    def _validate_type(self, value: Any) -> Any:
        """Enforce Python types.

        This method should be overridden by subclasses (e.g., `StringProperty`).

        Args:
            value (Any): The value to type-check.

        Returns:
            Any: The type-cast or verified value.
        """
        return value

    def _validate_single_value(self, instance: "Model", value: Any) -> Any:
        """Validate a single item through the full validation pipeline.

        The pipeline executes in this exact order:
        1. Type validation (`_validate_type`)
        2. Choices restriction (`choices`)
        3. Inline property validators (`validators=[...]`)
        4. Model-level field validators (`@field_validator('prop')`)

        Args:
            instance (Model): The model instance this property is attached to.
            value (Any): The specific value to validate.

        Raises:
            ValueError: If the value violates choices or a custom validation rule.
            TypeError: If the value violates the property's type constraint.

        Returns:
            Any: The fully validated and potentially coerced value.
        """
        value = self._validate_type(value)

        if self.choices is not None and value not in self.choices:
            raise ValueError(f"Value '{value}' must be one of {self.choices}")

        for validator in self.validators:
            value = validator(value)

        field_validator_methods = getattr(instance, "_field_validators", {}).get(self._python_name, [])
        for method_name in field_validator_methods:
            method = getattr(instance, method_name)
            value = method(value)

        return value

    def validate(self, instance: "Model", value: Any) -> Any:
        """Validate and process a value (or list of values) for this property.

        Handles `None` assignments, required checks, and maps the validation
        pipeline over elements if the property is `repeated`.

        Args:
            instance (Model): The underlying model instance.
            value (Any): The assigned value (or iterable if repeated).

        Raises:
            ValueError: If the property is required but None/empty is provided.
            TypeError: If a repeated property is assigned a non-iterable.

        Returns:
            Any: The fully validated value or list of validated values.
        """
        if value is None:
            if self.required:
                raise ValueError(f"Property '{self._python_name}' is required")
            return [] if self.repeated else None

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

    def __get__(self, instance: Optional["Model"], owner: type) -> Any:
        """Retrieve the property value from the model instance's internal dictionary.

        If accessed on the class itself, returns the Property descriptor instance.
        """
        if instance is None:
            return self
        # noinspection PyProtectedMember
        return instance._values.get(self._python_name, self.default)

    def __set__(self, instance: "Model", value: Any) -> None:
        """Validate and store the property value in the model instance's internal dictionary."""
        # noinspection PyProtectedMember
        instance._values[self._python_name] = self.validate(instance, value)

    def __delete__(self, instance: "Model") -> None:
        """Remove the property value from the model instance's internal dictionary."""
        # noinspection PyProtectedMember
        instance._values.pop(self._python_name, None)

    def _from_base_type(self, value: Any) -> Any:
        """
        Convert a value from the Datastore base type to the Python user type.

        By default, this is a simple pass-through. Subclasses (like JsonProperty)
        can override this to sanitize or cast data coming back from the database.
        """
        return value

    def _to_base_type(self, value: Any) -> Any:
        """
        Convert a value from the Python user type to the Datastore base type.

        By default, this is a simple pass-through. Subclasses can override this
        to cast data (e.g. casting a `date` to a `datetime`) before saving.
        """
        return value

    def _prepare_for_put(self, instance: "Model") -> None:
        """
        Hook that runs immediately before an instance is saved to Datastore.

        Useful for properties like DateTimeProperty to implement `auto_now`.
        """
        pass


class StringProperty(Property):
    """A Datastore property that strictly enforces string values."""

    def _validate_type(self, value: Any) -> Any:
        """Enforce that the value is a string.

        Args:
            value (Any): The value to check.

        Raises:
            TypeError: If the value is not an instance of `str`.

        Returns:
            str: The validated string.
        """
        if not isinstance(value, str):
            raise TypeError(f"Property '{self._python_name}' must be str")
        return value


class IntegerProperty(Property):
    """A Datastore property that strictly enforces integer values.

    Note: Python evaluates booleans as subclasses of integers (`isinstance(True, int)`
    is True). This descriptor explicitly rejects boolean values to maintain strict
    Datastore type integrity.
    """

    def _validate_type(self, value: Any) -> Any:
        """Enforce that the value is an integer and NOT a boolean.

        Args:
            value (Any): The value to check.

        Raises:
            TypeError: If the value is not an integer, or if it is a boolean.

        Returns:
            int: The validated integer.
        """
        if not isinstance(value, int) or isinstance(value, bool):
            raise TypeError(f"Property '{self._python_name}' must be int")
        return value


class BooleanProperty(Property):
    """A Datastore property that strictly enforces boolean values."""

    def _validate_type(self, value: Any) -> Any:
        """Enforce that the value is a boolean.

        Args:
            value (Any): The value to check.

        Raises:
            TypeError: If the value is not a bool.

        Returns:
            bool: The validated boolean.
        """
        if not isinstance(value, bool):
            raise TypeError(f"Property '{self._python_name}' must be a bool")
        return value


class FloatProperty(Property):
    """A Datastore property that enforces floating-point values.

    This property safely accepts both `float` and `int` types, automatically
    casting `int` assignments to `float` to prevent strict type errors over
    simple math (e.g. assigning `1` instead of `1.0`).
    """

    def _validate_type(self, value: Any) -> Any:
        """Enforce that the value is a float or integer.

        Args:
            value (Any): The value to check.

        Raises:
            TypeError: If the value is not an int/float, or if it is a boolean.

        Returns:
            float: The validated and cast floating-point number.
        """
        if not isinstance(value, (int, float)) or isinstance(value, bool):
            raise TypeError(f"Property '{self._python_name}' must be a float")
        return float(value)


class TextProperty(StringProperty):
    """A Datastore property for large strings.

    Identical to StringProperty, but safely defaults to `indexed=False`.
    Google Cloud Datastore imposes a 1500-byte limit on indexed strings.
    Use this property for article bodies, comments, and large blobs of text.
    """

    def __init__(self, **kwargs: Any):
        """Initialize the TextProperty, forcing indexed to False by default."""
        kwargs.setdefault("indexed", False)
        super().__init__(**kwargs)


class JsonProperty(Property):
    """A Datastore property that enforces JSON-serializable structures.

    This property acts as a safety net to ensure that complex nested structures
    (dicts, lists) are valid JSON. To prevent Datastore index explosion on
    arbitrarily nested keys, it defaults to `indexed=False`.

    Note: The underlying Google Cloud Datastore client will natively save these
    structures as `EmbeddedEntity` or `ListValue` items in the database.
    """

    def __init__(self, **kwargs: Any):
        """Initialize the JsonProperty, forcing indexed to False by default."""
        kwargs.setdefault("indexed", False)
        super().__init__(**kwargs)

    def _validate_type(self, value: Any) -> Any:
        """Enforce that the value is JSON-serializable."""
        try:
            json.dumps(value)
        except (TypeError, ValueError) as e:
            raise TypeError(f"Property '{self._python_name}' must be JSON serializable: {e}") from e
        return value

    def _from_base_type(self, value: Any) -> Any:
        """
        Sanitize the value coming back from the Datastore.

        Datastore natively converts nested dictionaries into `datastore.Entity`
        objects. This round-trips the data through JSON to recursively strip
        out those Datastore types and return pure Python primitives.
        """
        if value is None:
            return None

        return json.loads(json.dumps(value))


class DateTimeProperty(Property):
    """A Datastore property that enforces datetime values.

    If `tzinfo` is None, this expects naive datetimes and assumes UTC.
    If `tzinfo` is provided, it converts Datastore's UTC datetimes to that timezone.
    """

    def __init__(
            self,
            *,
            auto_now: bool = False,
            auto_now_add: bool = False,
            tzinfo: Optional[datetime.tzinfo] = None,
            **kwargs: Any
    ):
        """Initialize a new DateTimeProperty.

        Args:
            auto_now (bool): If True, automatically set to the current time on every put().
            auto_now_add (bool): If True, automatically set to the current time when first created.
            tzinfo (Optional[datetime.tzinfo]): The timezone to convert Datastore's UTC to/from.
            **kwargs (Any): Additional base property arguments (e.g., `name`, `required`, `indexed`).
        """
        self.auto_now = auto_now
        self.auto_now_add = auto_now_add
        self.tzinfo = tzinfo

        if kwargs.get('repeated') and (auto_now or auto_now_add):
            raise ValueError("auto_now and auto_now_add are incompatible with repeated properties.")

        super().__init__(**kwargs)

    def _prepare_for_put(self, instance: "Model") -> None:
        """Execute auto_now and auto_now_add logic."""
        if self.auto_now or (self.auto_now_add and getattr(instance, self._python_name) is None):
            now = datetime.datetime.now(self.tzinfo or datetime.timezone.utc)
            if self.tzinfo is None:
                now = now.replace(tzinfo=None)
            setattr(instance, self._python_name, now)

    def _validate_type(self, value: Any) -> Any:
        """Enforce that the value is a datetime."""
        if not isinstance(value, datetime.datetime):
            raise TypeError(f"Property '{self._python_name}' must be a datetime.datetime")
        if self.tzinfo is None and value.tzinfo is not None:
            raise ValueError(
                f"DateTimeProperty '{self._python_name}' without tzinfo can only support "
                f"naive datetimes (presumed UTC).")
        return value

    def _from_base_type(self, value: Any) -> Any:
        """Convert Datastore's UTC datetime to the expected timezone/naive state."""
        if value is None:
            return None

        if self.tzinfo is not None:
            if value.tzinfo is None:
                value = value.replace(tzinfo=datetime.timezone.utc)
            return value.astimezone(self.tzinfo)
        else:
            if value.tzinfo is not None:
                return value.replace(tzinfo=None)

        return value


class DateProperty(DateTimeProperty):
    """A Datastore property that enforces date values.

    Datastore only supports Datetimes, so this property casts to a Datetime
    at midnight UTC before saving, and casts back to a Date when reading.
    """

    def __init__(
            self,
            *,
            auto_now: bool = False,
            auto_now_add: bool = False,
            tzinfo: Optional[datetime.tzinfo] = None,
            **kwargs: Any
    ):
        """Initialize a new DateProperty.

        Args:
            auto_now (bool): If True, automatically set to the current date on every put().
            auto_now_add (bool): If True, automatically set to the current date when first created.
            tzinfo (Optional[datetime.tzinfo]): The timezone used to evaluate the "current" date.
            **kwargs (Any): Additional base property arguments (e.g., `name`, `required`, `indexed`).
        """
        super().__init__(auto_now=auto_now, auto_now_add=auto_now_add, tzinfo=tzinfo, **kwargs)

    def _validate_type(self, value: Any) -> Any:
        if not isinstance(value, datetime.date) or isinstance(value, datetime.datetime):
            raise TypeError(f"Property '{self._python_name}' must be a datetime.date")
        return value

    def _to_base_type(self, value: Any) -> Any:
        if value is None:
            return None
        return datetime.datetime(value.year, value.month, value.day, tzinfo=datetime.timezone.utc)

    def _from_base_type(self, value: Any) -> Any:
        if value is None:
            return None
        return value.date()

    def _prepare_for_put(self, instance: "Model") -> None:
        if self.auto_now or (self.auto_now_add and getattr(instance, self._python_name) is None):
            setattr(instance, self._python_name, datetime.datetime.now(datetime.timezone.utc).date())


class TimeProperty(DateTimeProperty):
    """A Datastore property that enforces time values.

    Datastore only supports Datetimes, so this property casts to a Datetime
    on Jan 1, 1970 UTC before saving, and casts back to a Time when reading.
    """

    def __init__(
            self,
            *,
            auto_now: bool = False,
            auto_now_add: bool = False,
            tzinfo: Optional[datetime.tzinfo] = None,
            **kwargs: Any
    ):
        """Initialize a new TimeProperty.

        Args:
            auto_now (bool): If True, automatically set to the current time on every put().
            auto_now_add (bool): If True, automatically set to the current time when first created.
            tzinfo (Optional[datetime.tzinfo]): The timezone used to evaluate the "current" time.
            **kwargs (Any): Additional base property arguments (e.g., `name`, `required`, `indexed`).
        """
        super().__init__(auto_now=auto_now, auto_now_add=auto_now_add, tzinfo=tzinfo, **kwargs)

    def _validate_type(self, value: Any) -> Any:
        if not isinstance(value, datetime.time):
            raise TypeError(f"Property '{self._python_name}' must be a datetime.time")
        return value

    def _to_base_type(self, value: Any) -> Any:
        if value is None:
            return None
        return datetime.datetime(1970, 1, 1, value.hour, value.minute, value.second, value.microsecond,
                                 tzinfo=datetime.timezone.utc)

    def _from_base_type(self, value: Any) -> Any:
        if value is None:
            return None
        return value.time()

    def _prepare_for_put(self, instance: "Model") -> None:
        if self.auto_now or (self.auto_now_add and getattr(instance, self._python_name) is None):
            setattr(instance, self._python_name, datetime.datetime.now(datetime.timezone.utc).time())
