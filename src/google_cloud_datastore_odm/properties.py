"""
Property descriptors for the Google Cloud Datastore ODM.

This module provides the base `Property` descriptor and its type-specific subclasses
(e.g., `StringProperty`, `IntegerProperty`, etc.). These classes handle data coercion,
validation, default values, and Datastore schema mapping.
"""

import base64
import datetime
import json
import pickle
import zlib
from typing import TYPE_CHECKING, Any, Callable

from google.cloud import datastore
from google.cloud.datastore.helpers import GeoPoint

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
            name: str | None = None,
            indexed: bool = True,
            repeated: bool = False,
            required: bool = False,
            default: Any = None,
            choices: list | None = None,
            validators: list[Callable] | None = None,
    ):
        """Initialize a new Property.

        Args:
            name (str | None): The Datastore column name. If omitted, defaults to
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
            choices (list | None): An optional list of allowed values. Assignments
                not in this list will raise a ValueError.
            validators (list[Callable] | None): A list of custom validation functions.
                Each function should accept a single value, validate/mutate it, and return it.

        Raises:
            TypeError: If any provided validator is not callable.

        Examples:
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
        self.validators: list[Callable] = validators or []

        if self.repeated and default is None:
            self.default = []
        else:
            self.default = default

        for validator in self.validators:
            if not callable(validator):
                raise TypeError(f"Validator {validator} for property '{self}' is not callable")

    def __set_name__(self, owner: type, name: str) -> None:
        """Called automatically by Python to set the attribute name."""
        self._python_name = name
        if not self.datastore_name:
            self.datastore_name = name

    def _validate_type(self, value: Any) -> Any:
        """Enforce Python types. This method should be overridden by subclasses."""
        return value

    def _validate_single_value(self, instance: "Model", value: Any) -> Any:
        """Validate a single item through the full validation pipeline."""
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

    def __get__(self, instance: "Model | None", owner: type) -> Any:
        """Retrieve the property value from the model instance's internal dictionary."""
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

    def serialize_value(self, value: Any) -> Any:
        """
        Convert the Python value into a JSON-safe primitive.

        By default, this is a simple pass-through. Subclasses containing complex
        types (e.g. datetimes, bytes, Datastore keys) must override this.
        """
        if value is None:
            return None
        return value

    def _prepare_for_put(self, instance: "Model") -> None:
        """Hook that runs immediately before an instance is saved to Datastore."""
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

    def in_(self, values: list | tuple | set):
        """Generates an 'IN' query filter."""
        from .query import FilterNode

        if not isinstance(values, (list, tuple, set)):
            raise TypeError("IN operator requires an iterable (list, tuple, set)")

        base_values = [self._to_base_type(v) for v in values]
        return FilterNode(self.datastore_name, "IN", base_values)

    def not_in_(self, values: list | tuple | set):
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

    Examples:
        ```python
        class Post(Model):
            # Restrict to keys of the 'Author' kind
            author_key = KeyProperty(kind="Author")
        ```
    """

    def __init__(
            self,
            kind: str | Any | None = None,
            *,
            name: str | None = None,
            indexed: bool = True,
            repeated: bool = False,
            required: bool = False,
            default: Any = None,
            choices: list | None = None,
            validators: list[Callable] | None = None,
    ):
        """Initialize a new KeyProperty.

        Args:
            kind (str | Any | None): A string or Model class to restrict
                the allowed keys. If provided, assigning a key of a different
                kind will raise a ValueError.
            name (str | None): The Datastore column name. Defaults to Python attribute name.
            indexed (bool): Whether the Datastore should index this property.
            repeated (bool): If True, expects an iterable of keys.
            required (bool): If True, assigning `None` will raise a ValueError.
            default (Any): The default value or a zero-argument callable to generate one.
            choices (list | None): An optional list of allowed values.
            validators (list[Callable] | None): A list of custom validation functions.
        """
        super().__init__(
            name=name,
            indexed=indexed,
            repeated=repeated,
            required=required,
            default=default,
            choices=choices,
            validators=validators
        )
        self._model = kind

    @property
    def expected_kind(self) -> str | None:
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

    def serialize_value(self, value: datastore.Key) -> str | None:
        if value is None:
            return None
        return value.to_legacy_urlsafe().decode('utf-8')


class BytesProperty(Property):
    """A Datastore property for raw byte data.

    This replaces the legacy `BlobProperty`. It is by default unindexed to bypass
    Datastore's 1500-byte limit for indexed properties. It also supports optional
    zlib compression to reduce storage costs for large binary payloads.

    Examples:
        ```python
        class FileUpload(Model):
            # Automatically compress large binary files before saving
            raw_data = BytesProperty(compressed=True)
        ```
    """

    def __init__(
            self,
            compressed: bool = False,
            *,
            name: str | None = None,
            indexed: bool | None = None,
            repeated: bool = False,
            required: bool = False,
            default: Any = None,
            choices: list | None = None,
            validators: list[Callable] | None = None,
    ):
        """Initialize a new BytesProperty.

        Args:
            compressed (bool): If True, automatically compress the bytes using zlib.
            name (str | None): The Datastore column name. Defaults to Python attribute name.
            indexed (bool | None): Defaults to False in order to bypass 1500-byte limits.
            repeated (bool): If True, expects an iterable of byte objects.
            required (bool): If True, assigning `None` will raise a ValueError.
            default (Any): The default value or a zero-argument callable to generate one.
            choices (list | None): An optional list of allowed values.
            validators (list[Callable] | None): A list of custom validation functions.
        """
        actual_indexed = indexed if indexed is not None else False

        if compressed and actual_indexed:
            raise ValueError("A BytesProperty cannot be both compressed and indexed.")

        super().__init__(
            name=name,
            indexed=actual_indexed,
            repeated=repeated,
            required=required,
            default=default,
            choices=choices,
            validators=validators
        )
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

    def serialize_value(self, value: bytes) -> str | None:
        if value is None:
            return None
        return base64.b64encode(value).decode('utf-8')


class PickleProperty(Property):
    """A Datastore property for storing arbitrary Python objects.

    Uses Python's built-in `pickle` module to serialize objects into bytes.
    It is by default unindexed to bypass Datastore's 1500-byte limit.

    **WARNING:** The `pickle` module is not secure. Only unpickle data you trust.
    For standard data structures, `JsonProperty` is highly recommended instead.

    Examples:
        ```python
        class GameState(Model):
            # Store complex Python objects natively
            inventory_set = PickleProperty(compressed=True)
        ```
    """

    def __init__(
            self,
            compressed: bool = False,
            *,
            name: str | None = None,
            indexed: bool | None = None,
            repeated: bool = False,
            required: bool = False,
            default: Any = None,
            choices: list | None = None,
            validators: list[Callable] | None = None,
    ):
        """Initialize a new PickleProperty.

        Args:
            compressed (bool): If True, automatically compress the pickled bytes using zlib.
            name (str | None): The Datastore column name. Defaults to Python attribute name.
            indexed (bool | None): Defaults to False in order to bypass 1500-byte limits.
            repeated (bool): If True, expects an iterable of Python objects.
            required (bool): If True, assigning `None` will raise a ValueError.
            default (Any): The default value or a zero-argument callable to generate one.
            choices (list | None): An optional list of allowed values.
            validators (list[Callable] | None): A list of custom validation functions.
        """
        actual_indexed = indexed if indexed is not None else False

        if compressed and actual_indexed:
            raise ValueError("A PickleProperty cannot be both compressed and indexed.")

        super().__init__(
            name=name,
            indexed=actual_indexed,
            repeated=repeated,
            required=required,
            default=default,
            choices=choices,
            validators=validators
        )
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

    def serialize_value(self, value: Any) -> str | None:
        if value is None:
            return None
        return base64.b64encode(pickle.dumps(value)).decode('utf-8')


class StringProperty(Property):
    """A Datastore property that strictly enforces string values.

    Examples:
        ```python
        class User(Model):
            username = StringProperty(required=True)
        ```
    """

    def _validate_type(self, value: Any) -> Any:
        if not isinstance(value, str):
            raise TypeError(f"Property '{self._python_name}' must be str")
        return value


class IntegerProperty(Property):
    """A Datastore property that strictly enforces integer values.

    Note: Python evaluates booleans as subclasses of integers (`isinstance(True, int)`
    is True). This descriptor explicitly rejects boolean values to maintain strict
    Datastore type integrity.

    Examples:
        ```python
        class Product(Model):
            stock_count = IntegerProperty(default=0)
        ```
    """

    def _validate_type(self, value: Any) -> Any:
        if not isinstance(value, int) or isinstance(value, bool):
            raise TypeError(f"Property '{self._python_name}' must be int")
        return value


class BooleanProperty(Property):
    """A Datastore property that strictly enforces boolean values.

    Examples:
        ```python
        class User(Model):
            is_active = BooleanProperty(default=True)
        ```
    """

    def _validate_type(self, value: Any) -> Any:
        if not isinstance(value, bool):
            raise TypeError(f"Property '{self._python_name}' must be a bool")
        return value


class FloatProperty(Property):
    """A Datastore property that enforces floating-point values.

    This property safely accepts both `float` and `int` types, automatically
    casting `int` assignments to `float` to prevent strict type errors over
    simple math (e.g. assigning `1` instead of `1.0`).

    Examples:
        ```python
        class Sensor(Model):
            temperature = FloatProperty()
        ```
    """

    def _validate_type(self, value: Any) -> Any:
        if not isinstance(value, (int, float)) or isinstance(value, bool):
            raise TypeError(f"Property '{self._python_name}' must be a float")
        return float(value)


class TextProperty(StringProperty):
    """A Datastore property for large strings.

    Unlike `StringProperty`, this is strictly unindexed to bypass Datastore's
    1500-byte limit. It also supports optional zlib compression for saving space.

    Examples:
        ```python
        class Article(Model):
            # Automatically compress large text blocks
            body = TextProperty(compressed=True)
        ```
    """

    def __init__(
            self,
            compressed: bool = False,
            *,
            name: str | None = None,
            indexed: bool | None = False,
            repeated: bool = False,
            required: bool = False,
            default: Any = None,
            choices: list | None = None,
            validators: list[Callable] | None = None,
    ):
        """Initialize a new TextProperty.

        Args:
            compressed (bool): If True, automatically compress the text string using zlib.
            name (str | None): The Datastore column name. Defaults to Python attribute name.
            indexed (bool | None): Text properties cannot be indexed. This must be False or None.
            repeated (bool): If True, expects an iterable of strings.
            required (bool): If True, assigning `None` will raise a ValueError.
            default (Any): The default value or a zero-argument callable to generate one.
            choices (list | None): An optional list of allowed values.
            validators (list[Callable] | None): A list of custom validation functions.
        """
        if indexed:
            raise ValueError("TextProperty cannot be indexed. Use StringProperty instead.")

        super().__init__(
            name=name,
            indexed=indexed,
            repeated=repeated,
            required=required,
            default=default,
            choices=choices,
            validators=validators
        )
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

    Examples:
        ```python
        class AuditLog(Model):
            # Store complex nested dictionaries securely
            payload = JsonProperty(compressed=True)
        ```
    """

    def __init__(
            self,
            compressed: bool = False,
            *,
            name: str | None = None,
            indexed: bool | None = None,
            repeated: bool = False,
            required: bool = False,
            default: Any = None,
            choices: list | None = None,
            validators: list[Callable] | None = None,
    ):
        """Initialize a new JsonProperty.

        Args:
            compressed (bool): If True, automatically compress the JSON string using zlib.
            name (str | None): The Datastore column name. Defaults to Python attribute name.
            indexed (bool | None): Defaults to False in order to prevent index explosions.
            repeated (bool): If True, expects an iterable of JSON-serializable objects.
            required (bool): If True, assigning `None` will raise a ValueError.
            default (Any): The default value or a zero-argument callable to generate one.
            choices (list | None): An optional list of allowed values.
            validators (list[Callable] | None): A list of custom validation functions.
        """
        actual_indexed = indexed if indexed is not None else False

        if compressed and actual_indexed:
            raise ValueError("A JsonProperty cannot be both compressed and indexed.")

        super().__init__(
            name=name,
            indexed=actual_indexed,
            repeated=repeated,
            required=required,
            default=default,
            choices=choices,
            validators=validators
        )
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

    If `tzinfo` is `None`, this expects naive datetimes and assumes UTC.
    If `tzinfo` is provided, it converts Datastore's UTC datetimes to that timezone.

    Examples:
        ```python
        class Article(Model):
            # Automatically populate on first save
            created_at = DateTimeProperty(auto_now_add=True, tzinfo=datetime.timezone.utc)

            # Automatically update on every save
            updated_at = DateTimeProperty(auto_now=True, tzinfo=datetime.timezone.utc)
        ```
    """

    def __init__(
            self,
            *,
            auto_now: bool = False,
            auto_now_add: bool = False,
            tzinfo: datetime.tzinfo | None = None,
            name: str | None = None,
            indexed: bool = True,
            repeated: bool = False,
            required: bool = False,
            default: Any = None,
            choices: list | None = None,
            validators: list[Callable] | None = None,
    ):
        """Initialize a new DateTimeProperty.

        Args:
            auto_now (bool): If True, automatically set to the current time on every put().
            auto_now_add (bool): If True, automatically set to the current time when first created.
            tzinfo (datetime.tzinfo | None): The timezone to convert Datastore's UTC to/from.
            name (str | None): The Datastore column name. Defaults to Python attribute name.
            indexed (bool): Whether the Datastore should index this property. Defaults to True.
            repeated (bool): If True, expects an iterable of datetimes.
            required (bool): If True, assigning `None` will raise a ValueError.
            default (Any): The default value or a zero-argument callable to generate one.
            choices (list | None): An optional list of allowed values.
            validators (list[Callable] | None): A list of custom validation functions.
        """
        self.auto_now = auto_now
        self.auto_now_add = auto_now_add
        self.tzinfo = tzinfo

        if repeated and (auto_now or auto_now_add):
            raise ValueError("auto_now and auto_now_add are incompatible with repeated properties.")

        super().__init__(
            name=name,
            indexed=indexed,
            repeated=repeated,
            required=required,
            default=default,
            choices=choices,
            validators=validators
        )

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
                f"naive datetimes (presumed UTC)."
            )
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

    def serialize_value(self, value: datetime.datetime) -> str | None:
        if value is None:
            return None
        return value.isoformat()


class DateProperty(DateTimeProperty):
    """A Datastore property that enforces date values.

    Datastore only supports Datetimes, so this property casts to a Datetime
    at midnight UTC before saving, and casts back to a Date when reading.

    Examples:
        ```python
        class Employee(Model):
            hire_date = DateProperty()
        ```
    """

    def __init__(
            self,
            *,
            auto_now: bool = False,
            auto_now_add: bool = False,
            tzinfo: datetime.tzinfo | None = None,
            name: str | None = None,
            indexed: bool = True,
            repeated: bool = False,
            required: bool = False,
            default: Any = None,
            choices: list | None = None,
            validators: list[Callable] | None = None,
    ):
        """Initialize a new DateProperty.

        Args:
            auto_now (bool): If True, automatically set to the current date on every put().
            auto_now_add (bool): If True, automatically set to the current date when first created.
            tzinfo (datetime.tzinfo | None): The timezone used to evaluate the "current" date.
            name (str | None): The Datastore column name. Defaults to Python attribute name.
            indexed (bool): Whether the Datastore should index this property.
            repeated (bool): If True, expects an iterable of dates.
            required (bool): If True, assigning `None` will raise a ValueError.
            default (Any): The default value or a zero-argument callable to generate one.
            choices (list | None): An optional list of allowed values.
            validators (list[Callable] | None): A list of custom validation functions.
        """
        super().__init__(
            auto_now=auto_now,
            auto_now_add=auto_now_add,
            tzinfo=tzinfo,
            name=name,
            indexed=indexed,
            repeated=repeated,
            required=required,
            default=default,
            choices=choices,
            validators=validators
        )

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
            tzinfo: datetime.tzinfo | None = None,
            name: str | None = None,
            indexed: bool = True,
            repeated: bool = False,
            required: bool = False,
            default: Any = None,
            choices: list | None = None,
            validators: list[Callable] | None = None,
    ):
        """Initialize a new TimeProperty.

        Args:
            auto_now (bool): If True, automatically set to the current time on every put().
            auto_now_add (bool): If True, automatically set to the current time when first created.
            tzinfo (datetime.tzinfo | None): The timezone used to evaluate the "current" time.
            name (str | None): The Datastore column name. Defaults to Python attribute name.
            indexed (bool): Whether the Datastore should index this property.
            repeated (bool): If True, expects an iterable of times.
            required (bool): If True, assigning `None` will raise a ValueError.
            default (Any): The default value or a zero-argument callable to generate one.
            choices (list | None): An optional list of allowed values.
            validators (list[Callable] | None): A list of custom validation functions.
        """
        super().__init__(
            auto_now=auto_now,
            auto_now_add=auto_now_add,
            tzinfo=tzinfo,
            name=name,
            indexed=indexed,
            repeated=repeated,
            required=required,
            default=default,
            choices=choices,
            validators=validators
        )

    def _validate_type(self, value: Any) -> Any:
        if not isinstance(value, datetime.time):
            raise TypeError(f"Property '{self._python_name}' must be a datetime.time")
        return value

    def _to_base_type(self, value: Any) -> Any:
        if value is None:
            return None
        return datetime.datetime(
            1970, 1, 1, value.hour, value.minute, value.second, value.microsecond,
            tzinfo=datetime.timezone.utc
        )

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

    Examples:
        ```python
        class Address(Model):
            city = StringProperty()

        class Profile(Model):
            # Embed the Address model completely
            location = StructuredProperty(Address)

        # Natively query embedded properties
        Profile.query().filter(Profile.location.city == "London")
        ```
    """

    def __init__(
            self,
            model_class: type["Model"],
            *,
            name: str | None = None,
            indexed: bool = True,
            repeated: bool = False,
            required: bool = False,
            default: Any = None,
            choices: list | None = None,
            validators: list[Callable] | None = None,
    ):
        """Initialize a new StructuredProperty.

        Args:
            model_class (type["Model"]): The class of the ODM Model to embed.
            name (str | None): The Datastore column name. Defaults to Python attribute name.
            indexed (bool): Whether the Datastore should index this property.
            repeated (bool): If True, expects an iterable of Model instances.
            required (bool): If True, assigning `None` will raise a ValueError.
            default (Any): The default value or a zero-argument callable to generate one.
            choices (list | None): An optional list of allowed values.
            validators (list[Callable] | None): A list of custom validation functions.
        """
        super().__init__(
            name=name,
            indexed=indexed,
            repeated=repeated,
            required=required,
            default=default,
            choices=choices,
            validators=validators
        )
        self.model_class = model_class

    def __getattr__(self, item: str) -> Any:
        """Intercept attribute access on the class level to build deep-query nodes!"""
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

    def serialize_value(self, value: "Model") -> dict | None:
        """Serialize the nested model into a JSON-safe dictionary."""
        if value is None:
            return None

        return value.to_json_dict()


class GeoPtProperty(Property):
    """A Datastore property for storing geographical coordinates (latitude and longitude).

    Accepts a native `google.cloud.datastore.helpers.GeoPoint`.

    Examples:
        ```python
        from google.cloud.datastore.helpers import GeoPoint

        class Landmark(Model):
            location = GeoPtProperty()

        eiffel_tower = Landmark(location=GeoPoint(48.8584, 2.2945))
        ```
    """

    def _validate_type(self, value: Any) -> Any:
        if not isinstance(value, GeoPoint):
            raise TypeError(
                f"Property '{self._python_name}' requires a native "
                f"google.cloud.datastore.helpers.GeoPoint instance. Got {type(value).__name__}."
            )
        return value

    def serialize_value(self, value: GeoPoint) -> dict | None:
        if value is None:
            return None
        return {"latitude": value.latitude, "longitude": value.longitude}


class GenericProperty(Property):
    """A Datastore property that can store any natively supported type dynamically.

    Acts as a schema-less field allowing you to store strings, integers, floats,
    booleans, datetimes, lists, or dictionaries without strict type enforcement.

    Supports `compressed=True`, which is only effective for `bytes` values and
    forces `indexed=False`.

    Examples:
        ```python
        class Webhook(Model):
            # Accept whatever payload the external service sends
            payload = GenericProperty()
        ```
    """

    def __init__(
            self,
            compressed: bool = False,
            *,
            name: str | None = None,
            indexed: bool | None = None,
            repeated: bool = False,
            required: bool = False,
            default: Any = None,
            choices: list | None = None,
            validators: list[Callable] | None = None,
    ):
        """Initialize a new GenericProperty.

        Args:
            compressed (bool): If True, compresses `bytes` values (forces `indexed=False`).
            name (str | None): The Datastore column name. Defaults to Python attribute name.
            indexed (bool | None): Whether the Datastore should index this property.
                Defaults to True unless compressed=True.
            repeated (bool): If True, expects an iterable of dynamic values.
            required (bool): If True, assigning `None` will raise a ValueError.
            default (Any): The default value or a zero-argument callable to generate one.
            choices (list | None): An optional list of allowed values.
            validators (list[Callable] | None): A list of custom validation functions.
        """
        actual_indexed = indexed if indexed is not None else (not compressed)

        if compressed and actual_indexed:
            raise ValueError(
                "A GenericProperty cannot be compressed and indexed at the same time."
            )

        super().__init__(
            name=name,
            indexed=actual_indexed,
            repeated=repeated,
            required=required,
            default=default,
            choices=choices,
            validators=validators
        )
        self.compressed = compressed

    def _to_base_type(self, value: Any) -> Any:
        if value is None:
            return None

        if self.compressed and isinstance(value, bytes):
            return zlib.compress(value)

        return value

    def _from_base_type(self, value: Any) -> Any:
        if value is None:
            return None

        if self.compressed and isinstance(value, bytes):
            return zlib.decompress(value)

        # If the developer saved a dictionary, the Google SDK sometimes returns
        # it wrapped in a `datastore.Entity` object. We cast it back to a pure
        # Python dict so the developer gets back exactly what they put in.
        if value.__class__.__name__ == 'Entity':
            return dict(value)

        return value

    def serialize_value(self, value: Any) -> Any:
        """
        Recursively serialize dynamic data into a JSON-safe structure.

        Because GenericProperty is schema-less, it must check for non-JSON-safe
        primitives (like datetimes or bytes) on the fly and cast them.
        """
        if value is None:
            return None

        if isinstance(value, (datetime.datetime, datetime.date, datetime.time)):
            return value.isoformat()

        if isinstance(value, bytes):
            return base64.b64encode(value).decode('utf-8')

        if isinstance(value, datastore.Key):
            return value.to_legacy_urlsafe().decode('utf-8')

        if isinstance(value, GeoPoint):
            return {"latitude": value.latitude, "longitude": value.longitude}

        if isinstance(value, (list, tuple, set)):
            return [self.serialize_value(item) for item in value]

        if isinstance(value, dict):
            return {k: self.serialize_value(v) for k, v in value.items()}

        return value


class ComputedProperty(GenericProperty):
    """A Property whose value is dynamically computed by a developer-supplied function.

    Cannot be assigned manually. The value is automatically evaluated when
    the property is accessed, or immediately before saving to the Datastore.

    Examples:
        ```python
        class Article(Model):
            content = TextProperty()

            @ComputedProperty
            def length(self):
                return len(self.content) if self.content else 0
        ```
    """

    def __init__(
            self,
            func: Callable | None = None,
            *,
            name: str | None = None,
            indexed: bool = True,
            repeated: bool = False,
            required: bool = False,
            default: Any = None,
            choices: list | None = None,
            validators: list[Callable] | None = None,
    ):
        """Initialize a new ComputedProperty.

        Args:
            func (Callable | None): The function to compute the property's value.
            name (str | None): The Datastore column name. Defaults to Python attribute name.
            indexed (bool): Whether the Datastore should index this property.
            repeated (bool): If True, expects an iterable.
            required (bool): If True, assigning `None` will raise a ValueError.
            default (Any): The default value or a zero-argument callable to generate one.
            choices (list | None): An optional list of allowed values.
            validators (list[Callable] | None): A list of custom validation functions.
        """
        super().__init__(
            compressed=False,
            name=name,
            indexed=indexed,
            repeated=repeated,
            required=required,
            default=default,
            choices=choices,
            validators=validators
        )
        self.func = func

    def __call__(self, func: Callable) -> "ComputedProperty":
        """Allows the property to be used as a decorator with arguments."""
        self.func = func
        return self

    def __get__(self, instance: Any, owner: Any) -> Any:
        if instance is None:
            return self

        # noinspection PyProtectedMember
        if getattr(instance, '_is_projected', False) and self._python_name in instance._values:
            # noinspection PyProtectedMember
            return instance._values[self._python_name]

        value = self.func(instance)
        # noinspection PyProtectedMember
        instance._values[self._python_name] = value
        return value

    def __set__(self, instance: Any, value: Any) -> None:
        """
        Allows the initial assignment so the ODM can hydrate fetched Datastore entities.
        Once the property is loaded into memory, it locks down to prevent manual mutation.
        """
        # noinspection PyProtectedMember
        if self._python_name in instance._values:
            raise AttributeError(f"Cannot assign to ComputedProperty '{self._python_name}'")

        # noinspection PyProtectedMember
        instance._values[self._python_name] = value

    def _prepare_for_put(self, instance: Any) -> None:
        # noinspection PyProtectedMember
        instance._values[self._python_name] = self.func(instance)
        super()._prepare_for_put(instance)
