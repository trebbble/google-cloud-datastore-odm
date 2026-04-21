"""
Core model definitions for the Google Cloud Datastore ODM.

This module provides the base `Model` class, its metaclass, and validation
decorators required to define and interact with Datastore entities.
"""

import copy
from collections import defaultdict
from typing import Any, Callable, ClassVar, Dict, Iterator, List, Optional, Tuple

from google.cloud import datastore

from .client import get_client
from .properties import Property
from .query import Query
from .transaction import get_current_transaction

MODEL_VALIDATOR_ATTR = "__model_validator__"
FIELD_VALIDATOR_ATTR = "__field_validator__"


def model_validator(func: Callable) -> Callable:
    """Decorator used to mark a method as a model-level validator.

    Model-level validators are executed when:
    - `Model.validate()` is called explicitly
    - `Model.put()` or `Model.put_multi()` is called

    They are NOT executed during instantiation or property assignment.

    Args:
        func (Callable): The method to decorate.

    Returns:
        Callable: The decorated method.
    """
    setattr(func, MODEL_VALIDATOR_ATTR, True)
    return func


def field_validator(field: str) -> Callable:
    """Decorator used to mark a method as a field-level validator.

    Field validators run automatically during property assignment,
    instantiation, and when calling `populate()`.

    Args:
        field (str): The name of the Python property this validates.

    Returns:
        Callable: A decorator for the specific validation method.
    """

    def decorator(func: Callable) -> Callable:
        setattr(func, FIELD_VALIDATOR_ATTR, field)
        return func

    return decorator


class ModelMeta(type):
    """Metaclass responsible for parsing and collecting model configurations.

    This runs once per model class at class creation time. It collects:
    - Property definitions
    - Model-level validators
    - Field-level validators
    - Datastore kind metadata and unindexed properties
    """

    def __new__(mcs, class_name: str, base_classes: Tuple[type, ...], class_attrs: Dict[str, Any]):
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

        meta_config = class_attrs.pop("Meta", None)
        datastore_project = None
        datastore_database = None
        datastore_namespace = None
        datastore_kind = class_name

        if meta_config:
            datastore_project = getattr(meta_config, "project", None)
            datastore_database = getattr(meta_config, "database", None)
            datastore_namespace = getattr(meta_config, "namespace", None)
            datastore_kind = getattr(meta_config, "kind", class_name)

        if not isinstance(datastore_kind, str):
            raise TypeError("Meta.kind must be a string")

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

        unindexed = set()
        for py_name, prop in collected_properties.items():
            if not prop.indexed:
                unindexed.add(prop.datastore_name or py_name)

        class_attrs["_properties"] = collected_properties
        class_attrs["_model_validators"] = collected_validators
        class_attrs["_field_validators"] = dict(collected_field_validators)
        class_attrs["_project"] = datastore_project
        class_attrs["_database"] = datastore_database
        class_attrs["_namespace"] = datastore_namespace
        class_attrs["_kind"] = datastore_kind
        class_attrs["_unindexed_datastore_names"] = frozenset(unindexed)

        return super().__new__(mcs, class_name, base_classes, class_attrs)


class Model(metaclass=ModelMeta):
    """Base ODM model for Google Cloud Datastore.

    Responsibilities:
    - Property validation and memory storage
    - Model-level and Field-level validation routing
    - Datastore persistence, mapping, and hydration
    - Lifecycle hook execution
    """
    _properties: ClassVar[Dict[str, Property]] = {}
    _model_validators: ClassVar[List[Callable]] = []
    _field_validators: ClassVar[Dict[str, List[str]]] = {}
    _project: ClassVar[Optional[str]] = None
    _database: ClassVar[Optional[str]] = None
    _namespace: ClassVar[Optional[str]] = None
    _kind: ClassVar[str]
    _unindexed_datastore_names: ClassVar[frozenset[str]] = frozenset()

    key: Optional[datastore.Key] = None

    @classmethod
    def _get_kwarg_or_alias(cls, kwargs: Dict[str, Any], keyword: str, default: Any = None) -> Any:
        """Extract Datastore routing metadata (id, parent) safely.

        If the user defined a property with a reserved name, they must use the
        `_` prefix (e.g., `_id=...`) to route to the Datastore Key.
        """
        alt_keyword = f"_{keyword}"
        if alt_keyword in kwargs:
            return kwargs.pop(alt_keyword)

        if keyword in kwargs and keyword not in cls._properties:
            return kwargs.pop(keyword)

        return default

    def __init__(self, **kwargs: Any) -> None:
        """Initialize a new model instance.

        Properties can be passed as keyword arguments.

        To explicitly set the Datastore key components, use the `id`, `parent`, or `key` kwargs.
        To explicitly set routing metadata use `project`, `database` and `namespace` kwargs.

        If your model has an actual property named after those keywords, prefix the routing kwargs with an underscore:
         `_id`, `_parent`, `_project`, `_database`, `_namespace`

        'key' is reserved and prohibited from being used as a property name but if you have an actual Datastore
        field called 'key' you can still access it by using the alias feature.

        Args:
            **kwargs: Property values and Datastore routing metadata

        Raises:
            ValueError: If a required property is missing.
            AttributeError: If an unknown property is provided.
        """
        self._values: Dict[str, Any] = {}

        self._is_projected = kwargs.pop("_is_projected", False)

        _id = self._get_kwarg_or_alias(kwargs, "id")
        parent = self._get_kwarg_or_alias(kwargs, "parent")
        project = self._get_kwarg_or_alias(kwargs, "project")
        database = self._get_kwarg_or_alias(kwargs, "database")
        namespace = self._get_kwarg_or_alias(kwargs, "namespace")
        key = kwargs.pop("key", None)

        if _id is not None:
            self.key = self.key_from_id(_id, parent=parent, project=project, database=database, namespace=namespace)
        else:
            self.key = key
            if self.key is None and any(x is not None for x in (parent, project, database, namespace)):
                resolved_proj = project if project is not None else self._project
                resolved_db = database if database is not None else self._database
                resolved_ns = namespace if namespace is not None else self._namespace

                key_kwargs = {}
                if parent:
                    key_kwargs["parent"] = parent
                if resolved_ns:
                    key_kwargs["namespace"] = resolved_ns

                client = self.client(project=resolved_proj, database=resolved_db)
                self.key = client.key(self._kind, **key_kwargs)

        for property_name, _property in self._properties.items():
            if property_name in kwargs:
                setattr(self, property_name, kwargs.pop(property_name))
            elif not self._is_projected and _property.default is not None:
                if callable(_property.default):
                    default_val = _property.default()
                else:
                    try:
                        default_val = copy.deepcopy(_property.default)
                    except TypeError:
                        default_val = _property.default
                setattr(self, property_name, default_val)

        if kwargs:
            raise AttributeError(f"Unknown properties provided to {self.__class__.__name__}: {list(kwargs.keys())}")

    def __repr__(self) -> str:
        """Return a string representation of the model instance."""
        meta_parts = []

        if self._kind != self.__class__.__name__:
            meta_parts.append(f"kind={self._kind!r}")

        project = self.key.project if self.key else self._project
        database = self.key.database if self.key else self._database
        namespace = self.key.namespace if self.key else self._namespace

        if project:
            meta_parts.append(f"project={project!r}")
        if database:
            meta_parts.append(f"database={database!r}")
        if namespace:
            meta_parts.append(f"namespace={namespace!r}")

        meta_str = f"Meta({', '.join(meta_parts)})" if meta_parts else ""
        id_str = f"id={self.key.id_or_name!r}" if self.key and self.key.id_or_name else ""

        property_repr = ", ".join(
            f"{name}={value!r}" for name, value in self._values.items()
        )

        parts = [self.__class__.__name__]
        if meta_str:
            parts.append(meta_str)
        if id_str:
            parts.append(id_str)
        if property_repr:
            parts.append(property_repr)

        return f"<{' '.join(parts)}>"

    def __eq__(self, other: Any) -> bool:
        """Strictly compare two entities for equality.

        To be equal, both the Datastore Keys AND the unsaved memory states must match exactly.
        """
        if not isinstance(other, self.__class__):
            return NotImplemented

        if self.key != other.key:
            return False

        return self._values == other._values

    def __getitem__(self, key: str) -> Any:
        """Allow dictionary-style read access to properties."""
        return self._values[key]

    def __setitem__(self, key: str, value: Any) -> None:
        """Allow dictionary-style write access to properties (triggers validation)."""
        setattr(self, key, value)

    def __iter__(self) -> Iterator[str]:
        """Iterate over the property names set on the model."""
        return iter(self._values)

    def items(self) -> Any:
        """Return a view of the model's property names and values."""
        return self._values.items()

    def to_dict(self, include: Optional[List[str]] = None, exclude: Optional[List[str]] = None) -> Dict[str, Any]:
        """Return a shallow dictionary representation of the model properties.

        Args:
            include (Optional[List[str]]): If provided, only include these Python property names.
            exclude (Optional[List[str]]): If provided, exclude these Python property names.

        Returns:
            Dict[str, Any]: A dictionary mapping Python property names to their current values.
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
        """Execute all model-level validators.

        Property-level validation automatically occurs during standard assignment. This
        method runs methods decorated with `@model_validator` to verify cross-property logic.
        """
        for validator in self._model_validators:
            validator(self)

    @classmethod
    def kind(cls) -> str:
        """Return the Datastore kind associated with this model class."""
        return cls._kind

    @classmethod
    def get_schema(cls, output_format: str = "full") -> Any:
        """Introspect the model's schema and property configuration.

        Args:
            output_format (str): The format of the returned schema.
                - "full" (default): Dict[str, dict] with JSON-serializable configurations.
                - "properties": List[Property] instances.
                - "named_properties": Dict[str, Property] instances.
                - "property_names": List[str] of Python property names.
                - "property_aliases": Dict[str, str] mapping Python names to Datastore names.

        Returns:
            Any: The schema in the requested format.
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

    @classmethod
    def allocate_ids(
            cls,
            size: int,
            parent: Optional[datastore.Key] = None,
            project: Optional[str] = None,
            database: Optional[str] = None,
            namespace: Optional[str] = None
    ) -> List[datastore.Key]:
        """Allocate a batch of integer IDs for this model's kind.

        Reserves a block of numeric IDs directly from the Datastore backend. This is
        useful for generating guaranteed-unique IDs before instantiating objects.

        Args:
            size (int): The number of IDs to allocate. Must be > 0.
            parent (Optional[datastore.Key]): An optional ancestor key for the allocated IDs.
            project (Optional[str]): An optional project override.
            database (Optional[str]): An optional database override.
            namespace (Optional[str]): An optional namespace override.

        Returns:
            List[datastore.Key]: A list of fully resolved keys with allocated integer IDs.

        Raises:
            ValueError: If the requested size is 0 or negative.
        """
        if size <= 0:
            raise ValueError("Number of IDs to allocate must be greater than 0.")

        resolved_proj = project if project is not None else cls._project
        resolved_db = database if database is not None else cls._database
        client = cls.client(project=resolved_proj, database=resolved_db)

        kwargs = {}

        resolved_ns = namespace if namespace is not None else cls._namespace
        if resolved_ns:
            kwargs["namespace"] = resolved_ns

        if parent:
            kwargs["parent"] = parent

        incomplete_key = client.key(cls._kind, **kwargs)
        return client.allocate_ids(incomplete_key, num_ids=size)

    def allocate_key(self, parent: Optional[datastore.Key] = None) -> datastore.Key:
        """Explicitly allocate a complete datastore key for this specific instance.

        Triggers a single RPC call to the Datastore to fetch an integer ID.

        Args:
            parent (Optional[datastore.Key]): An optional ancestor key.

        Returns:
            datastore.Key: The newly allocated, fully resolved Key.
        """
        if self.key is None or self.key.is_partial:
            actual_proj = self.key.project if self.key else self._project
            actual_db = self.key.database if self.key else self._database
            actual_ns = self.key.namespace if self.key else self._namespace
            actual_parent = parent or (self.key.parent if self.key else None)

            self.key = self.allocate_ids(
                size=1,
                parent=actual_parent,
                project=actual_proj,
                database=actual_db,
                namespace=actual_ns
            )[0]

        return self.key

    def _ensure_key(self) -> None:
        """Ensure the model has at least an incomplete key before persistence.

        Does NOT trigger an RPC call. The Datastore backend will auto-assign
        the ID natively during the put() operation.
        """
        if self.key is None:
            kwargs = {}

            if self._namespace:
                kwargs["namespace"] = self._namespace

            client = self.client(project=self._project, database=self._database)
            self.key = client.key(self._kind, **kwargs)

    @classmethod
    def client(cls, project: Optional[str] = None, database: Optional[str] = None) -> datastore.Client:
        """Retrieve the configured active Datastore client."""
        return get_client(project=project, database=database)

    @classmethod
    def key_from_id(
            cls,
            identifier: Any,
            parent: Optional[datastore.Key] = None,
            project: Optional[str] = None,
            database: Optional[str] = None,
            namespace: Optional[str] = None
    ) -> datastore.Key:
        """Construct a datastore Key for this model's kind.

        Args:
            identifier (Any): The string or integer ID for the entity.
            parent (Optional[datastore.Key]): An optional ancestor key.
            project (Optional[str]): An optional project override.
            database (Optional[str]): An optional database override.
            namespace (Optional[str]): An optional namespace override.

        Returns:
            datastore.Key: The constructed Key object.
        """
        kwargs = {}
        if parent:
            kwargs["parent"] = parent

        resolved_proj = project if project is not None else cls._project
        resolved_db = database if database is not None else cls._database

        resolved_ns = namespace if namespace is not None else cls._namespace
        if resolved_ns:
            kwargs["namespace"] = resolved_ns

        client = cls.client(project=resolved_proj, database=resolved_db)
        return client.key(cls._kind, identifier, **kwargs)

    def populate(self, **kwargs: Any) -> None:
        """Update multiple properties at once.

        Triggers all descriptor and field validators during assignment.

        Args:
            **kwargs: Property names and their new values.

        Raises:
            AttributeError: If an unknown property is provided.
        """
        for key, value in kwargs.items():
            if key in self._properties:
                setattr(self, key, value)
            else:
                raise AttributeError(f"Unknown property: {key}")

    @classmethod
    def from_entity(cls, entity: Optional[datastore.Entity], _is_projected: bool = False) -> Optional["Model"]:
        """Create a model instance from a raw datastore Entity.

        Args:
            entity (Optional[datastore.Entity]): The retrieved Datastore entity.

        Returns:
            Optional[Model]: A hydrated Python model instance, or None if no entity was provided.
        """
        if entity is None:
            return None

        kwargs = {"_is_projected": _is_projected}

        for py_name, prop in cls._properties.items():
            if prop.datastore_name in entity:
                raw_value = entity[prop.datastore_name]

                if prop.repeated and isinstance(raw_value, list):
                    # noinspection PyProtectedMember
                    kwargs[py_name] = [prop._from_base_type(v) for v in raw_value]
                else:
                    # noinspection PyProtectedMember
                    kwargs[py_name] = prop._from_base_type(raw_value)

        safe_key = getattr(entity, 'key', None)
        return cls(key=safe_key, **kwargs)

    @classmethod
    def _pre_get_hook(cls, key: datastore.Key) -> None:
        """Runs just before a read request is sent to the Datastore."""
        pass

    @classmethod
    def _post_get_hook(cls, key: datastore.Key, instance: Optional["Model"]) -> None:
        """Runs immediately after an entity is fetched and hydrated into a Python object.

        Args:
            key (datastore.Key): The key that was requested.
            instance (Optional[Model]): The hydrated model instance, or None if the
                entity did not exist in the Datastore.
        """
        pass

    def _pre_put_hook(self) -> None:
        """Runs just before the entity is sent to the Datastore."""
        pass

    def _post_put_hook(self) -> None:
        """Runs immediately after the entity successfully saves and receives its key."""
        pass

    @classmethod
    def _pre_delete_hook(cls, key: datastore.Key) -> None:
        """Runs just before the delete request is sent to the Datastore."""
        pass

    @classmethod
    def _post_delete_hook(cls, key: datastore.Key) -> None:
        """Runs immediately after the delete request succeeds."""
        pass

    @classmethod
    def get(cls, key: datastore.Key) -> Optional["Model"]:
        """Fetch an entity by its Datastore key and hydrate a model instance.

        Executes the `_pre_get_hook` before fetching, and the `_post_get_hook`
        after hydration (even if the entity was not found).

        Args:
            key (datastore.Key): The Google Cloud Datastore Key to fetch.

        Returns:
            Optional[Model]: The hydrated model instance, or None if not found.
        """
        cls._pre_get_hook(key)

        client = cls.client(project=key.project, database=key.database)
        txn = get_current_transaction()

        entity = client.get(key, transaction=txn)

        instance = cls.from_entity(entity) if entity else None
        cls._post_get_hook(key, instance)

        return instance

    @classmethod
    def get_by_id(cls, identifier: Any, parent: Optional[datastore.Key] = None) -> Optional["Model"]:
        """Fetch an entity by its string or integer ID.

        Args:
            identifier (Any): The string name or integer ID.
            parent (Optional[datastore.Key]): An optional ancestor key.

        Returns:
            Optional[Model]: The hydrated model instance, or None if not found.
        """
        return cls.get(cls.key_from_id(identifier, parent))

    @classmethod
    def query(
            cls,
            project: Optional[str] = None,
            database: Optional[str] = None,
            namespace: Optional[str] = None
    ) -> Query:
        """Create a Query object for this model's Datastore kind.

        Args:
            project (Optional[str]): An optional project override.
            database (Optional[str]): An optional database override.
            namespace (Optional[str]): An optional namespace override.

        Returns:
            Query: An ODM Query object ready for filtering and fetching.
        """
        resolved_proj = project if project is not None else cls._project
        resolved_db = database if database is not None else cls._database
        resolved_ns = namespace if namespace is not None else cls._namespace

        return Query(cls, project=resolved_proj, database=resolved_db, namespace=resolved_ns)

    def _check_completeness(self):
        """
        Ensures no required fields are missing
        """
        for py_name, prop in self._properties.items():
            if not prop.required:
                continue

            value = getattr(self, py_name)

            if value in (None, []):
                raise ValueError(f"Property '{py_name}' is required")

    def put(self, exclude_from_indexes: Optional[List[str]] = None) -> datastore.Key:
        """Persist the model instance to the Datastore.

        Triggers model-level validation and runs the `_pre_put_hook` and `_post_put_hook`.
        If the instance does not have a complete key, Datastore auto-assigns an ID natively.

        Args:
            exclude_from_indexes (Optional[List[str]]): An optional list of Python property
                names (or even raw datastore fields) to dynamically exclude
                from Datastore indexes for this specific write.

        Returns:
            datastore.Key: The fully resolved Datastore Key.
        """
        if self._is_projected:
            raise RuntimeError("Cannot save an entity fetched via a Projection query. This would cause data loss.")

        self._check_completeness()
        self.validate()
        self._ensure_key()

        txn = get_current_transaction()

        if txn and self.key.is_partial:
            self.allocate_key()

        self._pre_put_hook()

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
            # noinspection PyProtectedMember
            prop._prepare_for_put(self)

            value = self._values.get(py_name)

            if value is not None:
                if prop.repeated:
                    # noinspection PyProtectedMember
                    entity[prop.datastore_name] = [prop._to_base_type(v) for v in value]
                else:
                    # noinspection PyProtectedMember
                    entity[prop.datastore_name] = prop._to_base_type(value)

        if txn:
            txn.put(entity)
        else:
            client = self.client(project=self.key.project, database=self.key.database)
            client.put(entity)
            self.key = entity.key

        self._post_put_hook()

        return self.key

    def delete(self) -> None:
        """Delete the model instance from the Datastore.

        Executes the `_pre_delete_hook` before deletion and `_post_delete_hook` after.

        Raises:
            ValueError: If the entity does not have a key.
        """
        if self.key is None:
            raise ValueError("Cannot delete an entity that does not have a key.")

        self._pre_delete_hook(self.key)

        txn = get_current_transaction()
        if txn:
            executor = txn
        else:
            executor = self.client(project=self.key.project, database=self.key.database)

        executor.delete(self.key)
        self._post_delete_hook(self.key)

    @classmethod
    def get_multi(cls, keys: List[datastore.Key]) -> List[Optional["Model"]]:
        """Fetch multiple entities by their keys in a single RPC call.

        Returns a list of model instances in the exact order of the provided keys.
        Missing entities are represented as `None` in the returned list.

        Args:
            keys (List[datastore.Key]): A list of Datastore keys to fetch.

        Returns:
            List[Optional[Model]]: Hydrated instances or None, preserving input order.
        """
        if not keys:
            return []

        project = keys[0].project
        database = keys[0].database
        if any(k.project != project or k.database != database for k in keys):
            raise ValueError("All keys in a get_multi operation must belong to the same project and database.")

        for key in keys:
            cls._pre_get_hook(key)

        client = cls.client(project=project, database=database)
        txn = get_current_transaction()

        entities = client.get_multi(keys, transaction=txn)
        entity_map = {e.key: e for e in entities}

        instances = []
        for key in keys:
            instance = cls.from_entity(entity_map.get(key))
            cls._post_get_hook(key, instance)
            instances.append(instance)

        return instances

    @classmethod
    def put_multi(cls, instances: List["Model"]) -> List[datastore.Key]:
        """Persist multiple model instances in a single batch Datastore operation.

        This is significantly faster and more cost-effective than calling `.put()`
        in a loop. Hooks (`_pre_put_hook`, `_post_put_hook`) and validators are
        triggered for each instance.

        Args:
            instances (List[Model]): A list of unsaved or modified model instances.

        Returns:
            List[datastore.Key]: A list of keys corresponding to the saved entities.
        """
        if not instances:
            return []

        if any(inst._is_projected for inst in instances):
            raise RuntimeError("Cannot save an entity fetched via a Projection query. This would cause data loss.")

        for instance in instances:
            instance._ensure_key()

        project = instances[0].key.project
        database = instances[0].key.database
        if any(inst.key.project != project or inst.key.database != database for inst in instances):
            raise ValueError("All instances in a put_multi operation must belong to the same project and database.")

        txn = get_current_transaction()

        if txn:
            allocation_groups = defaultdict(list)
            for inst in instances:
                if inst.key.is_partial:
                    allocation_groups[(inst.key.parent, inst.key.namespace)].append(inst)

            for (parent, namespace), group_instances in allocation_groups.items():
                allocated_keys = cls.allocate_ids(
                    size=len(group_instances),
                    parent=parent,
                    project=project,
                    database=database,
                    namespace=namespace
                )
                for inst, alloc_key in zip(group_instances, allocated_keys):
                    inst.key = alloc_key

        entities_to_put = []

        # Use the pre-computed schema-level index exclusions for maximum speed
        unindexed_names = tuple(cls._unindexed_datastore_names)

        for instance in instances:
            instance._check_completeness()
            instance.validate()
            instance._pre_put_hook()

            entity = datastore.Entity(
                key=instance.key,
                exclude_from_indexes=unindexed_names
            )

            for py_name, prop in cls._properties.items():
                # noinspection PyProtectedMember
                prop._prepare_for_put(instance)
                value = instance._values.get(py_name)

                if value is not None:
                    if prop.repeated:
                        # noinspection PyProtectedMember
                        entity[prop.datastore_name] = [prop._to_base_type(v) for v in value]
                    else:
                        # noinspection PyProtectedMember
                        entity[prop.datastore_name] = prop._to_base_type(value)

            entities_to_put.append(entity)

        if txn:
            for entity in entities_to_put:
                txn.put(entity)
        else:
            client = cls.client(project=project, database=database)
            client.put_multi(entities_to_put)

            for instance, entity in zip(instances, entities_to_put):
                instance.key = entity.key

        for instance in instances:
            instance._post_put_hook()

        return [instance.key for instance in instances]

    @classmethod
    def delete_multi(cls, keys: List[datastore.Key]) -> None:
        """Delete multiple entities by their keys in a single batch Datastore operation.

        Args:
            keys (List[datastore.Key]): A list of fully resolved Datastore Keys to delete.
        """
        if not keys:
            return

        project = keys[0].project
        database = keys[0].database
        if any(k.project != project or k.database != database for k in keys):
            raise ValueError("All keys in a delete_multi operation must belong to the same project and database.")

        for key in keys:
            cls._pre_delete_hook(key)

        txn = get_current_transaction()
        if txn:
            for key in keys:
                txn.delete(key)
        else:
            client = cls.client(project=project, database=database)
            client.delete_multi(keys)

        for key in keys:
            cls._post_delete_hook(key)
