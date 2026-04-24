# Validation & Lifecycle Hooks

When building robust applications, ensuring data integrity is just as important as saving it. The Google Cloud Datastore ODM provides a multi-tiered validation pipeline and a comprehensive set of lifecycle hooks to intercept database operations.

---

## The Validation Pipeline

Data validation in the ODM occurs in three distinct phases. You can mix and match these depending on the complexity of your rules.

1. **Property-Level Constraints:** Built-in checks like `required=True`, `choices=[...]`, and strict type enforcement.
2. **Field-Level Validators:** Custom functions that run immediately whenever a specific property is assigned a value.
3. **Model-Level Validators:** Complex, cross-property checks that run right before the entity is saved to the database.

Here is a comprehensive model utilizing all three layers:

```python
from google_cloud_datastore_odm import (
    Model, StringProperty, IntegerProperty, 
    field_validator, model_validator
)

# A reusable inline validator
def no_emoji_allowed(value: str) -> str:
    for char in value:
        if ord(char) > 127:
            raise ValueError(f"Value '{value}' contains non-ASCII characters.")
    return value

class Article(Model):
    # 1. Built-in Constraints & Inline Validators
    title = StringProperty(required=True)
    status = StringProperty(default="draft", choices=["draft", "published"])
    clean_notes = StringProperty(validators=[no_emoji_allowed])
    word_count = IntegerProperty(default=0)

    # 2. Field-Level Validators
    @field_validator("title")
    def validate_title(self, value: str) -> str:
        if len(value) < 3 or len(value) > 200:
            raise ValueError("Title must be between 3 and 200 characters.")
        return value.strip() # You can modify and clean data here!

    # 3. Model-Level Validators
    @model_validator
    def validate_published_requires_content(self):
        if self.status == "published" and (self.word_count or 0) == 0:
            raise ValueError("A published article must have a word count > 0")
```

---

## The Execution Lifecycle

Understanding the exact order in which validators and hooks run is critical for debugging complex data mutations. The ODM strictly enforces a deterministic lifecycle separated into two phases:

### Phase 1: The Assignment Phase (In-Memory)
Whenever you assign a value to a property (e.g., `doc.title = "Hello"` or via the `__init__` constructor), the following pipeline runs **immediately**:

1. **Type Coercion:** Ensures the base type matches (e.g., casting an `int` to a `float`).
2. **Choices Enforcement:** Checks if the value exists in the `choices=[...]` list.
3. **Inline Validators:** `validators=[...]` run in the exact order they are defined.
4. **Field Validators:** `@field_validator` methods run last, acting as the final authority on the sanitized input.

!!! note
    Because Phase 1 runs instantly in memory, assigning bad data (like an emoji to `clean_notes`) will immediately raise a `ValueError` in your Python code, long before `.put()` is ever called.

### Phase 2: The Persistence Phase (Database Save)
When you call `.put()` or `.put_multi()`, the ODM strictly separates business logic validation from database side effects. The timeline looks like this:

1. **Completeness Check:** Ensures no `required=True` properties are missing.
2. **Model Validators:** `@model_validator` methods run. If any fail, the operation aborts here.
3. **Key Resolution:** If the entity is new, a partial Datastore Key is generated.
4. **Pre-Put Hook (`_pre_put_hook`):** Executes now. The model is proven valid and guaranteed to attempt a save.
5. **Property Serialization:** Descriptors prepare data for the Datastore (e.g., `auto_now` timestamps generate their current time right here).
6. **The RPC Call:** Data is physically sent to the Google Cloud Datastore backend.
7. **Post-Put Hook (`_post_put_hook`):** Executes *only* if the database write was completely successful.

---

## Lifecycle Hooks

Sometimes you need to trigger side effects when database operations occur. For example: logging audit trails, invalidating caches, sending webhooks, or updating search indexes.

The ODM exposes 6 native hooks you can override:

* **Read Hooks:** `_pre_get_hook`, `_post_get_hook`
* **Write Hooks:** `_pre_put_hook`, `_post_put_hook`
* **Delete Hooks:** `_pre_delete_hook`, `_post_delete_hook`

!!! note
    To use a hook, simply define the method on your model. Note that `get` and `delete` hooks must be `@classmethod`s because they often run before an instance even exists in memory.

```python
class TrackedTask(Model):
    description = StringProperty()

    # --- Write Hooks (Instance Methods) ---
    def _pre_put_hook(self):
        print(f"Preparing to save task: {self.description}")
        # Ideal place to update 'last_modified' timestamps manually

    def _post_put_hook(self):
        print(f"Successfully saved task with ID: {self.key.id_or_name}")
        # Ideal place to trigger event-driven webhooks

    # --- Read Hooks (Class Methods) ---
    @classmethod
    def _pre_get_hook(cls, key):
        print(f"Preparing to fetch key: {key.id_or_name}")

    @classmethod
    def _post_get_hook(cls, key, instance):
        print(f"Fetched key: {key.id_or_name}. Found instance? {instance is not None}")
        # Ideal place to decrypt sensitive fields coming from the DB

    # --- Delete Hooks (Class Methods) ---
    @classmethod
    def _pre_delete_hook(cls, key):
        print(f"Preparing to delete key: {key.id_or_name}")

    @classmethod
    def _post_delete_hook(cls, key):
        print(f"Successfully deleted key: {key.id_or_name}")
        # Ideal place to remove associated files from Cloud Storage
```

Hooks execute seamlessly during standard `.put()`, `.get()`, and `.delete()` calls, as well as their batch `_multi` counterparts.

