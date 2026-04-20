"""
Property descriptors for the Google Cloud Datastore ODM.

This module provides the base `Property` descriptor and its type-specific subclasses
(e.g., `StringProperty`, `IntegerProperty`). These classes handle data coercion,
validation, default values, and Datastore schema mapping.
"""

import datetime
import json
import pickle
import zlib
from typing import TYPE_CHECKING, Any, Callable, List, Optional, Union

from google.cloud import datastore

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
            return [] if self.repeated else None

        if self.repeated:
            if not isinstance(value, (list, tuple, set)):
                raise TypeError(f"Property '{self._python_name}' is repeated and requires an iterable")

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
        if instance._is_projected and self._python_name not in instance._values:
            raise AttributeError(
                f"Cannot access property '{self._python_name}' on '{owner.__name__}'. "
                f"This entity was loaded via a Projection query and this field was not requested."
            )

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

    def _comparison(self, op: str, value: Any) -> Any:
        """Internal helper to generate a FilterNode for queries."""
        from .query import FilterNode

        if value is not None:
            value = self._to_base_type(value)

        return FilterNode(self.datastore_name, op, value)

    def __eq__(self, value: Any):
        return self._comparison("=", value)

    def __ne__(self, value: Any):
        return self._comparison("!=", value)

    def __lt__(self, value: Any):
        return self._comparison("<", value)

    def __le__(self, value: Any):
        return self._comparison("<=", value)

    def __gt__(self, value: Any):
        return self._comparison(">", value)

    def __ge__(self, value: Any):
        return self._comparison(">=", value)

    def in_(self, values: list):
        """Generates an 'IN' query filter."""
        from .query import FilterNode

        if not isinstance(values, (list, tuple, set)):
            raise TypeError("IN operator requires an iterable (list, tuple, set)")

        base_values = [self._to_base_type(v) for v in values]

        return FilterNode(self.datastore_name, "IN", base_values)

    def not_in_(self, values: list):
        """Generates a 'NOT IN' query filter."""
        from .query import FilterNode

        if not isinstance(values, (list, tuple, set)):
            raise TypeError("NOT_IN operator requires an iterable (list, tuple, set)")

        base_values = [self._to_base_type(v) for v in values]

        return FilterNode(self.datastore_name, "NOT_IN", base_values)

    def __neg__(self):
        """Allows descending order queries using the unary minus: -Article.age"""
        from .query import OrderNode

        return OrderNode(self.datastore_name, descending=True)

    def __pos__(self):
        """Allows explicit ascending order queries: +Article.age"""
        from .query import OrderNode

        return OrderNode(self.datastore_name, descending=False)

    IN = in_
    NOT_IN = not_in_


class KeyProperty(Property):
    """A Datastore property that enforces Datastore Key values.

    This property acts as a foreign key to create relationships between entities.
    It can optionally be restricted to only accept keys of a specific entity kind.
    """

    def __init__(self, kind: Optional[Union[str, Any]] = None, **kwargs: Any):
        """Initialize a new KeyProperty.

        Args:
            kind (Optional[Union[str, Any]]): A string or Model class to restrict
                the allowed keys. If provided, assigning a key of a different
                kind will raise a ValueError.
            **kwargs: Additional base property arguments.
        """
        super().__init__(**kwargs)
        self._model = kind

    @property
    def expected_kind(self) -> Optional[str]:
        """Resolve the expected kind string from a string or Model class."""
        if self._model is None:
            return None

        if isinstance(self._model, str):
            return self._model

        if hasattr(self._model, "kind") and callable(self._model.kind):
            return self._model.kind()

        return self._model.__name__

    def _validate_type(self, value: Any) -> Any:
        """Enforce that the value is a Datastore Key of the correct kind."""
        if not isinstance(value, datastore.Key):
            raise TypeError(f"Property '{self._python_name}' must be a google.cloud.datastore.Key")

        expected = self.expected_kind
        if expected and value.kind != expected:
            raise ValueError(
                f"Property '{self._python_name}' expected a Key of kind '{expected}', "
                f"but got '{value.kind}'"
            )

        return value


class BytesProperty(Property):
    """A Datastore property for raw byte data.

    This replaces the legacy `BlobProperty`. It is by default unindexed to bypass
    Datastore's 1500-byte limit for indexed properties. It also supports optional
    zlib compression to reduce storage costs for large binary payloads.
    """

    def __init__(self, compressed: bool = False, **kwargs: Any):
        kwargs.setdefault("indexed", False)

        if compressed and kwargs.get("indexed"):
            raise ValueError("A BytesProperty cannot be both compressed and indexed.")

        kwargs["indexed"] = False
        super().__init__(**kwargs)
        self.compressed = compressed

    def _validate_type(self, value: Any) -> Any:
        if not isinstance(value, bytes):
            raise TypeError(f"Property '{self._python_name}' requires bytes.")
        return value

    def _to_base_type(self, value: Any) -> Any:
        if value is None:
            return None

        if self.compressed:
            return zlib.compress(value)
        return value

    def _from_base_type(self, value: Any) -> Any:
        if value is None:
            return None

        if self.compressed and isinstance(value, bytes):
            return zlib.decompress(value)
        return value


class PickleProperty(Property):
    """A Datastore property for storing arbitrary Python objects.

    Uses Python's built-in `pickle` module to serialize objects into bytes.
    It is by default unindexed to bypass Datastore's 1500-byte limit.

    WARNING: The `pickle` module is not secure. Only unpickle data you trust.
    For standard data structures, `JsonProperty` is highly recommended instead.
    """

    def __init__(self, compressed: bool = False, **kwargs: Any):
        kwargs.setdefault("indexed", False)

        if compressed and kwargs.get("indexed"):
            raise ValueError("A PickleProperty cannot be both compressed and indexed.")

        kwargs["indexed"] = False
        super().__init__(**kwargs)
        self.compressed = compressed

    def _to_base_type(self, value: Any) -> Any:
        if value is None:
            return None

        pickled_data = pickle.dumps(value)

        if self.compressed:
            return zlib.compress(pickled_data)
        return pickled_data

    def _from_base_type(self, value: Any) -> Any:
        if value is None:
            return None

        if self.compressed and isinstance(value, bytes):
            value = zlib.decompress(value)

        return pickle.loads(value)


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

    Unlike StringProperty, this is strictly unindexed to bypass Datastore's
    1500-byte limit. It also supports optional zlib compression for saving space.
    """

    def __init__(self, compressed: bool = False, **kwargs: Any):
        if kwargs.get("indexed"):
            raise ValueError("TextProperty cannot be indexed. Use StringProperty instead.")

        kwargs["indexed"] = False
        super().__init__(**kwargs)
        self.compressed = compressed

    def _to_base_type(self, value: Any) -> Any:
        if not isinstance(value, str):
            raise TypeError(f"Property '{self._python_name}' requires a string.")

        if self.compressed:
            return zlib.compress(value.encode('utf-8'))
        return value

    def _from_base_type(self, value: Any) -> str:
        if self.compressed and isinstance(value, bytes):
            return zlib.decompress(value).decode('utf-8')
        return value


class JsonProperty(Property):
    """A Datastore property that enforces JSON-serializable structures.

    This property defaults to `indexed=False` to prevent Datastore
    index explosions on arbitrarily nested dynamic keys. It also supports
    optional zlib compression to drastically reduce storage costs for massive
    JSON payloads.
    """

    def __init__(self, compressed: bool = False, **kwargs: Any):
        kwargs.setdefault("indexed", False)

        if compressed and kwargs.get("indexed"):
            raise ValueError("A JsonProperty cannot be both compressed and indexed.")

        kwargs["indexed"] = False
        super().__init__(**kwargs)
        self.compressed = compressed

    def _validate_type(self, value: Any) -> Any:
        """Enforce that the value is JSON-serializable."""
        try:
            json.dumps(value)
        except (TypeError, ValueError) as e:
            raise TypeError(f"Property '{self._python_name}' must be JSON serializable: {e}") from e
        return value

    def _to_base_type(self, value: Any) -> Any:
        """Sanitize and optionally compress the data before saving."""
        if value is None:
            return None

        try:
            json_str = json.dumps(value)
        except (TypeError, ValueError) as e:
            raise TypeError(f"Property '{self._python_name}' must be JSON serializable: {e}") from e

        if self.compressed:
            return zlib.compress(json_str.encode('utf-8'))

        return json.loads(json_str)

    def _from_base_type(self, value: Any) -> Any:
        """
        Decompress (if needed) and sanitize data coming from Datastore.

        Datastore natively converts nested dictionaries into `datastore.Entity`
        objects. This round-trips the data through JSON to recursively strip
        out those Datastore types and return pure Python primitives.
        """
        if value is None:
            return None

        if self.compressed and isinstance(value, bytes):
            json_str = zlib.decompress(value).decode('utf-8')
            return json.loads(json_str)

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


class NestedPropertyProxy(Property):
    """A proxy descriptor for querying nested properties inside a StructuredProperty.

    This magically inherits all the Property query operators and perfectly
    maps nested datastore keys (e.g. 'address.city').
    """

    def __init__(self, parent_datastore_name: str, nested_prop: Property):
        super().__init__(name=f"{parent_datastore_name}.{nested_prop.datastore_name}")
        self.nested_prop = nested_prop

    def _to_base_type(self, value: Any) -> Any:
        """Route the value through the nested property's Datastore hook."""
        # noinspection PyProtectedMember
        return self.nested_prop._to_base_type(value)


class StructuredProperty(Property):
    """A Datastore property that embeds another Model instance.

    Maps directly to Datastore's `EmbeddedEntity` data type. Nested models are
    fully hydrated, validated, and natively queryable using dot-notation.
    """

    def __init__(self, model_class: type["Model"], **kwargs: Any):
        super().__init__(**kwargs)
        self.model_class = model_class

    def __getattr__(self, item: str) -> Any:
        """
        Intercept attribute access on the class level to build deep-query nodes!
        Example: Article.author_info.city == "London"
        """
        # noinspection PyProtectedMember
        if hasattr(self.model_class, '_properties') and item in self.model_class._properties:

            if self.repeated:
                raise ValueError(
                    f"Datastore does not support querying sub-properties of a repeated "
                    f"StructuredProperty ('{self.datastore_name}'). Deep queries only work on "
                    f"singular embedded entities."
                )

            # noinspection PyProtectedMember
            nested_prop = self.model_class._properties[item]
            return NestedPropertyProxy(self.datastore_name, nested_prop)

        raise AttributeError(f"'{self.__class__.__name__}' object has no attribute '{item}'")

    def _validate_type(self, value: Any) -> Any:
        if not isinstance(value, self.model_class):
            raise TypeError(
                f"Property '{self._python_name}' requires instance of {self.model_class.__name__}"
            )
        return value

    def _to_base_type(self, value: Any) -> Any:
        if value is None:
            return None

        # noinspection PyProtectedMember
        value._check_completeness()
        value.validate()
        # noinspection PyProtectedMember
        value._pre_put_hook()

        # noinspection PyProtectedMember
        unindexed_names = set(value._unindexed_datastore_names)
        if not self.indexed:
            # If the parent is unindexed, ADD all known children to the unindexed set!
            # noinspection PyProtectedMember
            unindexed_names.update(p.datastore_name for p in value._properties.values())

        embedded_entity = datastore.Entity(exclude_from_indexes=tuple(unindexed_names))

        # noinspection PyProtectedMember
        for py_name, prop in value._properties.items():
            # noinspection PyProtectedMember
            prop._prepare_for_put(value)
            # noinspection PyProtectedMember
            val = value._values.get(py_name)

            if val is not None:
                if prop.repeated:
                    # noinspection PyProtectedMember
                    embedded_entity[prop.datastore_name] = [prop._to_base_type(v) for v in val]
                else:
                    # noinspection PyProtectedMember
                    embedded_entity[prop.datastore_name] = prop._to_base_type(val)

        return embedded_entity

    def _from_base_type(self, value: Any) -> Any:
        if value is None:
            return None

        if isinstance(value, dict) and not isinstance(value, datastore.Entity):
            ent = datastore.Entity()
            ent.update(value)
            value = ent

        return self.model_class.from_entity(value)
