import copy
from collections import defaultdict
from typing import Any, Callable, ClassVar, Dict, List, Optional

from google.cloud import datastore

from .client import get_client
from .properties import Property
from .query import Query

MODEL_VALIDATOR_ATTR = "__model_validator__"
FIELD_VALIDATOR_ATTR = "__field_validator__"


def model_validator(func: Callable) -> Callable:
    """
    Decorator used to mark a method as a model-level validator.

    Model-level validators are executed when:
    - Model.validate() is called explicitly
    - Model.put() is called

    They are NOT executed during instantiation or property assignment.
    """
    setattr(func, MODEL_VALIDATOR_ATTR, True)
    return func


def field_validator(field: str) -> Callable:
    """
    Decorator used to mark a method as a field validator.
    """

    def decorator(func: Callable) -> Callable:
        setattr(func, FIELD_VALIDATOR_ATTR, field)
        return func

    return decorator


class ModelMeta(type):
    """
    Metaclass responsible for collecting:
    - Property definitions
    - Model-level validators
    - Field-level validators
    - Datastore kind metadata

    This runs once per model class at class creation time.
    """

    def __new__(mcs, class_name, base_classes, class_attrs):
        collected_properties: Dict[str, Property] = {}
        collected_validators: List[Callable] = []
        collected_field_validators: Dict[str, List[str]] = defaultdict(list)

        # Inherit properties and validators from base classes
        for base_class in base_classes:
            collected_properties.update(getattr(base_class, "_properties", {}))
            collected_validators.extend(getattr(base_class, "_model_validators", []))

            for field, methods in getattr(base_class, "_field_validators", {}).items():
                collected_field_validators[field].extend(methods)

        _reserved_names = {"key"}

        # Collect properties and validators
        for attribute_name, attribute_value in class_attrs.items():
            if isinstance(attribute_value, Property):
                if attribute_name in _reserved_names:
                    raise ValueError(
                        f"Property name '{attribute_name}' on '{class_name}' is reserved by the ODM. "
                        f"If you need to map to a Datastore field named '{attribute_name}', "
                        f"use a different Python attribute name and the alias feature: e.g., "
                        f"custom_{attribute_name} = Property(name='{attribute_name}')"
                    )
                collected_properties[attribute_name] = attribute_value

            if getattr(attribute_value, MODEL_VALIDATOR_ATTR, False):
                if not callable(attribute_value):
                    raise TypeError(
                        f"Model validator '{attribute_name}' on class '{class_name}' is not callable"
                    )
                collected_validators.append(attribute_value)

            field_name = getattr(attribute_value, FIELD_VALIDATOR_ATTR, None)
            if field_name:
                if not callable(attribute_value):
                    raise TypeError(
                        f"Field validator '{attribute_name}' on class '{class_name}' is not callable"
                    )
                collected_field_validators[field_name].append(attribute_name)

        datastore_kind = class_attrs.get("__kind__", class_name)
        if not isinstance(datastore_kind, str):
            raise TypeError("__kind__ must be a string")

        unindexed = set()
        for py_name, prop in collected_properties.items():
            if not prop.indexed:
                unindexed.add(prop.datastore_name or py_name)

        class_attrs["_properties"] = collected_properties
        class_attrs["_model_validators"] = collected_validators
        class_attrs["_field_validators"] = dict(collected_field_validators)
        class_attrs["_kind"] = datastore_kind
        class_attrs["_unindexed_datastore_names"] = frozenset(unindexed)

        return super().__new__(mcs, class_name, base_classes, class_attrs)


class Model(metaclass=ModelMeta):
    """
    Base ODM model for Google Cloud Datastore.

    Responsibilities:
    - Property validation and storage
    - Model-level validation
    - Datastore persistence
    - Entity hydration
    """
    _properties: ClassVar[Dict[str, Property]] = {}
    _model_validators: ClassVar[List[Callable]] = []
    _field_validators: ClassVar[Dict[str, List[str]]] = {}
    _kind: ClassVar[str]
    _unindexed_datastore_names: ClassVar[frozenset[str]] = frozenset()

    key: Optional[datastore.Key] = None

    @classmethod
    def _get_kwarg_or_alias(cls, kwargs: Dict[str, Any], keyword: str, default: Any = None) -> Any:
        """
        Extract Datastore routing metadata (id, parent) safely.
        If the user defined a property with this name, they must use the `_` prefix
        (e.g., `_id=...`) to route to the Datastore Key.
        """
        alt_keyword = f"_{keyword}"
        if alt_keyword in kwargs:
            return kwargs.pop(alt_keyword)

        if keyword in kwargs and keyword not in cls._properties:
            return kwargs.pop(keyword)

        return default

    def __init__(self, **kwargs: Any) -> None:
        """
        Initialize a model instance.
        """
        self._values: Dict[str, Any] = {}

        _id = self._get_kwarg_or_alias(kwargs, "id")
        parent = self._get_kwarg_or_alias(kwargs, "parent")
        key = kwargs.pop("key", None)

        if _id is not None:
            self.key = self.key_from_id(_id, parent=parent)
        else:
            self.key = key
            if self.key is None and parent is not None:
                self.key = self._client().key(self._kind, parent=parent)

        for property_name, _property in self._properties.items():
            if property_name in kwargs:
                setattr(self, property_name, kwargs.pop(property_name))
            elif _property.default is not None:
                if callable(_property.default):
                    default_val = _property.default()
                else:
                    try:
                        default_val = copy.deepcopy(_property.default)
                    except TypeError:
                        default_val = _property.default
                setattr(self, property_name, default_val)
            elif _property.required:
                raise ValueError(f"{property_name} is required")

        if kwargs:
            raise AttributeError(f"Unknown properties provided to {self.__class__.__name__}: {list(kwargs.keys())}")

    def __repr__(self) -> str:
        property_repr = ", ".join(
            f"{name}={value!r}" for name, value in self._values.items()
        )
        key_part = ""
        if self.key and self.key.id_or_name:
            key_part = f" id={self.key.id_or_name!r}"
        return f"<{self.__class__.__name__}{key_part} {property_repr}>"

    def __getitem__(self, key: str) -> Any:
        return self._values[key]

    def __setitem__(self, key: str, value: Any) -> None:
        setattr(self, key, value)

    def __iter__(self):
        return iter(self._values)

    def items(self):
        return self._values.items()

    def to_dict(self, include: Optional[List[str]] = None,  exclude: Optional[List[str]] = None) -> Dict[str, Any]:
        """
        Return a shallow dictionary representation of the model properties.
        """
        result = {}
        for py_name in self._properties:
            if include and py_name not in include:
                continue
            if exclude and py_name in exclude:
                continue

            result[py_name] = self._values.get(py_name)

        return result

    def validate(self) -> None:
        """
        Execute all model-level validators.

        Property-level validation has already occurred during assignment.
        """
        for validator in self._model_validators:
            validator(self)

    @classmethod
    def kind(cls) -> str:
        return cls._kind

    @classmethod
    def get_schema(cls, output_format: str = "full") -> Any:
        """
        Public API for model introspection.

        Args:
            output_format:
                - "full" (default): Returns Dict[str, dict] with JSON-serializable configurations.
                - "properties": Returns List[Property] instances.
                - "named_properties": Returns Dict[str, Property] instances.
                - "property_names": Returns List[str] of Python property names.
                - "property_aliases": Returns Dict[str, str] mapping Python names to Datastore names.
        """
        valid_formats = (
            "properties",
            "named_properties",
            "property_names",
            "property_aliases",
            "full"
        )

        if output_format == "properties":
            return list(cls._properties.values())

        elif output_format == "property_names":
            return list(cls._properties.keys())

        elif output_format == "named_properties":
            return cls._properties

        elif output_format == "property_aliases":
            return {
                py_name: prop.datastore_name
                for py_name, prop in cls._properties.items()
            }

        elif output_format == "full":
            schema = {}
            for py_name, prop in cls._properties.items():
                schema[py_name] = {
                    "type": prop.__class__.__name__,
                    "datastore_name": prop.datastore_name,
                    "required": prop.required,
                    "repeated": prop.repeated,
                    "indexed": prop.indexed,
                    "choices": prop.choices,
                    "default": prop.default if not callable(prop.default) else f"<callable: {prop.default.__name__}>"
                }
            return schema

        else:
            raise ValueError(
                f"Unknown output format '{output_format}'. Must be one of {valid_formats}"
            )

    def allocate_key(self, parent: Optional[datastore.Key] = None) -> datastore.Key:
        """
        Explicitly allocate a datastore key for this model instance.
        """
        if self.key is None:
            incomplete_key = self._client().key(self._kind, parent=parent)
            self.key = self._client().allocate_ids(incomplete_key, num_ids=1)[0]

        return self.key

    def _ensure_key(self) -> None:
        """Ensure the model has a key before persistence."""
        if self.key is None:
            self.allocate_key()

    @classmethod
    def _client(cls) -> datastore.Client:
        return get_client()

    @classmethod
    def key_from_id(
            cls,
            identifier: Any,
            parent: Optional[datastore.Key] = None,
    ) -> datastore.Key:
        """Construct a datastore Key for this model's kind."""
        return cls._client().key(cls._kind, identifier, parent=parent)

    @classmethod
    def get(cls, key: datastore.Key):
        """Fetch an entity by its datastore key and hydrate a model instance."""
        entity = cls._client().get(key)
        return cls.from_entity(entity) if entity else None

    @classmethod
    def get_by_id(cls, identifier: Any, parent: Optional[datastore.Key] = None):
        """Fetch an entity by its ID or name."""
        return cls.get(cls.key_from_id(identifier, parent))

    @classmethod
    def query(cls) -> Query:
        """Create a query object for this model."""
        return Query(cls)

    def put(self, exclude_from_indexes: Optional[List[str]] = None):
        """
        Persist the model instance to datastore.
        Args:
            exclude_from_indexes: Optional list of Python property names to
                                  dynamically exclude from Datastore indexes for this specific write.
        """
        self.validate()
        self._ensure_key()
        client = self._client()

        unindexed_names = set(self._unindexed_datastore_names)

        if exclude_from_indexes:
            for name in exclude_from_indexes:
                if name in self._properties:
                    unindexed_names.add(self._properties[name].datastore_name)
                else:
                    unindexed_names.add(name)

        entity = datastore.Entity(
            key=self.key,
            exclude_from_indexes=tuple(unindexed_names)
        )

        for py_name, prop in self._properties.items():
            value = self._values.get(py_name)

            if value is not None:
                entity[prop.datastore_name] = value

        client.put(entity)
        return self

    def populate(self, **kwargs: Any) -> None:
        """
        Update multiple properties at once.
        Triggers all field validators during assignment.
        """
        for key, value in kwargs.items():
            if key in self._properties:
                setattr(self, key, value)
            else:
                raise AttributeError(f"Unknown property: {key}")

    @classmethod
    def from_entity(cls, entity: Optional[datastore.Entity]):
        """Create a model instance from a datastore Entity."""
        if entity is None:
            return None

        kwargs = {}

        for py_name, prop in cls._properties.items():
            if prop.datastore_name in entity:
                kwargs[py_name] = entity[prop.datastore_name]

        instance = cls(key=entity.key, **kwargs)
        return instance
