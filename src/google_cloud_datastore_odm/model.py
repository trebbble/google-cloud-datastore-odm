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

            # Inherit field validators
            for field, methods in getattr(base_class, "_field_validators", {}).items():
                collected_field_validators[field].extend(methods)

        # Collect properties and validators
        for attribute_name, attribute_value in class_attrs.items():
            if isinstance(attribute_value, Property):
                collected_properties[attribute_name] = attribute_value

            if getattr(attribute_value, MODEL_VALIDATOR_ATTR, False):
                if not callable(attribute_value):
                    raise TypeError(
                        f"Model validator '{attribute_name}' on class '{class_name}' is not callable"
                    )
                collected_validators.append(attribute_value)

            # Collect field validators
            field_name = getattr(attribute_value, FIELD_VALIDATOR_ATTR, None)
            if field_name:
                if not callable(attribute_value):
                    raise TypeError(
                        f"Field validator '{attribute_name}' on class '{class_name}' is not callable"
                    )
                collected_field_validators[field_name].append(attribute_name)

        # Resolve datastore kind
        datastore_kind = class_attrs.get("__kind__", class_name)
        if not isinstance(datastore_kind, str):
            raise TypeError("__kind__ must be a string")

        # Inject collected metadata into the class
        class_attrs["_properties"] = collected_properties
        class_attrs["_model_validators"] = collected_validators
        class_attrs["_field_validators"] = dict(collected_field_validators)
        class_attrs["_kind"] = datastore_kind

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
    # --- metaclass-injected attributes (declared for type checkers) ---
    _properties: ClassVar[Dict[str, Property]] = {}
    _model_validators: ClassVar[List[Callable]] = []
    _field_validators: ClassVar[Dict[str, List[str]]] = {}
    _kind: ClassVar[str]

    key: Optional[datastore.Key] = None

    def __init__(self, **kwargs: Any) -> None:
        """
        Initialize a model instance.
        """
        self._values: Dict[str, Any] = {}

        # 1. Key generation (Support for NDB-style id=...)
        _id = kwargs.pop("id", None)
        parent = kwargs.pop("parent", None)

        if _id:
            self.key = self.key_from_id(_id, parent=parent) # 130
        else:
            self.key = kwargs.pop("key", None)

        # 2. Populate properties
        for property_name, _property in self._properties.items():
            if property_name in kwargs:
                setattr(self, property_name, kwargs.pop(property_name))
            elif _property.default is not None:
                # 1. If the default is a callable (like `list` or `datetime.utcnow`), call it!
                if callable(_property.default):
                    default_val = _property.default() # 141
                else:
                    # 2. Otherwise, safely deepcopy to prevent shared references in lists/dicts
                    try:
                        default_val = copy.deepcopy(_property.default)
                    except TypeError:
                        default_val = _property.default  # Fallback
                setattr(self, property_name, default_val)
            elif _property.required:
                raise ValueError(f"{property_name} is required")

        # Optional: Raise error on unknown properties for strict schemas
        if kwargs:
            raise AttributeError(f"Unknown properties provided to {self.__class__.__name__}: {list(kwargs.keys())}")

    def __repr__(self) -> str:
        property_repr = ", ".join(
            f"{name}={value!r}" for name, value in self._values.items()
        )
        key_part = f" id={self.id!r}" if self.key else ""
        return f"<{self.__class__.__name__}{key_part} {property_repr}>"

    def __getitem__(self, key: str) -> Any:
        return self._values[key]

    def __setitem__(self, key: str, value: Any) -> None:
        setattr(self, key, value)

    def __iter__(self):
        return iter(self._values)

    def items(self):
        return self._values.items()

    def to_dict(self) -> Dict[str, Any]:
        """
        Return a shallow dictionary representation of the model properties.
        """
        return dict(self._values)

    def validate(self) -> None:
        """
        Execute all model-level validators.

        Property-level validation has already occurred during assignment.
        """
        for validator in self._model_validators:
            validator(self)

    @property
    def has_key(self) -> bool:
        """Return True if the model instance has a datastore key assigned."""
        return self.key is not None

    @property
    def id(self) -> Optional[Any]:
        """Return the entity identifier (id or name) if a key exists."""
        if self.key is None:
            return None
        return self.key.id or self.key.name

    @classmethod
    def kind(cls) -> str:
        return cls._kind

    def allocate_key(self, parent: Optional[datastore.Key] = None) -> datastore.Key:
        """
        Explicitly allocate a datastore key for this model instance.
        """
        if self.key is None:
            self.key = self._client().key(self._kind, parent=parent)
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

    def put(self):
        """
        Persist the model instance to datastore.
        """
        self.validate()
        self._ensure_key()
        client = self._client()

        # Gather unindexed properties
        unindexed_names = [
            prop._datastore_name for prop in self._properties.values() if not prop.indexed
        ]

        entity = datastore.Entity(
            key=self.key,
            exclude_from_indexes=tuple(unindexed_names)
        )

        for py_name, prop in self._properties.items():
            value = self._values.get(py_name)

            # Write to Datastore using the datastore_name
            if value is not None:
                entity[prop._datastore_name] = value

        client.put(entity)
        self.key = entity.key
        return self

    @classmethod
    def from_entity(cls, entity: Optional[datastore.Entity]):
        """Create a model instance from a datastore Entity."""
        if entity is None:
            return None

        kwargs = {}

        # Read from Datastore using the datastore_name, but instantiate using the python_name
        for py_name, prop in cls._properties.items():
            if prop._datastore_name in entity:
                kwargs[py_name] = entity[prop._datastore_name]

        instance = cls(key=entity.key, **kwargs)
        return instance
