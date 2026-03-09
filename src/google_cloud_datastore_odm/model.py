from typing import Any, Callable, ClassVar, Dict, List, Optional

from google.cloud import datastore

from .client import get_client
from .fields import Field
from .query import Query

MODEL_VALIDATOR_ATTR = "__model_validator__"


def model_validator(func: Callable) -> Callable:
    """
    Decorator used to mark a method as a model-level validator.

    Model-level validators are executed when:
    - Model.validate() is called explicitly
    - Model.put() is called

    They are NOT executed during instantiation or field assignment.
    """
    setattr(func, MODEL_VALIDATOR_ATTR, True)
    return func


class ModelMeta(type):
    """
    Metaclass responsible for collecting:
    - Field definitions
    - Model-level validators
    - Datastore kind metadata

    This runs once per model class at class creation time.
    """

    def __new__(mcs, class_name, base_classes, class_attrs):
        collected_fields: Dict[str, Field] = {}
        collected_validators: List[Callable] = []

        # Inherit fields and model validators from base classes
        for base_class in base_classes:
            collected_fields.update(getattr(base_class, "_fields", {}))
            collected_validators.extend(getattr(base_class, "_model_validators", []))

        # Collect fields and model-level validators
        for attribute_name, attribute_value in class_attrs.items():
            if isinstance(attribute_value, Field):
                collected_fields[attribute_name] = attribute_value

            if getattr(attribute_value, MODEL_VALIDATOR_ATTR, False):
                if not callable(attribute_value):
                    raise TypeError(
                        f"Model validator '{attribute_name}' on class '{class_name}' is not callable"
                    )
                collected_validators.append(attribute_value)

        # Resolve datastore kind
        datastore_kind = class_attrs.get("__kind__", class_name)
        if not isinstance(datastore_kind, str):
            raise TypeError("__kind__ must be a string")

        # Inject collected metadata into the class
        class_attrs["_fields"] = collected_fields
        class_attrs["_model_validators"] = collected_validators
        class_attrs["_kind"] = datastore_kind

        return super().__new__(mcs, class_name, base_classes, class_attrs)


class Model(metaclass=ModelMeta):
    """
    Base ODM model for Google Cloud Datastore.

    Responsibilities:
    - Field validation and storage
    - Model-level validation
    - Datastore persistence
    - Entity hydration
    """

    # --- metaclass-injected attributes (declared for type checkers) ---
    _fields: ClassVar[Dict[str, Field]] = {}
    _model_validators: ClassVar[List[Callable]] = []
    _kind: ClassVar[str]

    # Datastore entity key (identity)
    key: Optional[datastore.Key] = None

    def __init__(self, **kwargs: Any) -> None:
        """
        Initialize a model instance.

        Field values are validated on assignment.
        The datastore key may be optionally provided via `key=...`.
        """
        self._values: Dict[str, Any] = {}

        # Extract datastore key if provided
        self.key = kwargs.pop("key", None)

        # Populate fields, apply defaults and enforce required ones
        for field_name, field in self._fields.items():
            if field_name in kwargs:
                setattr(self, field_name, kwargs[field_name])
            elif field.default is not None:
                setattr(self, field_name, field.default)
            elif field.required:
                raise ValueError(f"{field_name} is required")

    def __repr__(self) -> str:
        field_repr = ", ".join(
            f"{name}={value!r}" for name, value in self._values.items()
        )
        key_part = f" id={self.id!r}" if self.key else ""
        return f"<{self.__class__.__name__}{key_part} {field_repr}>"

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
        Return a shallow dictionary representation of the model fields.
        """
        return dict(self._values)

    def validate(self) -> None:
        """
        Execute all model-level validators.

        Field-level validation has already occurred during assignment.
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

        Executes model-level validation before writing.
        """
        self.validate()

        self._ensure_key()

        client = self._client()
        entity = datastore.Entity(key=self.key)

        for field_name in self._fields:
            value = self._values.get(field_name)
            if value is not None:
                entity[field_name] = value

        client.put(entity)
        self.key = entity.key
        return self

    @classmethod
    def from_entity(cls, entity: Optional[datastore.Entity]):
        """Create a model instance from a datastore Entity."""
        if entity is None:
            return None

        instance = cls(**entity)
        instance.key = entity.key
        return instance
