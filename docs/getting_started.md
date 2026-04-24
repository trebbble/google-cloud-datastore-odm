# Getting Started

Welcome to the Google Cloud Datastore ODM! This guide will walk you through installing the library, connecting to your database, and performing your first basic CRUD operations.

## Installation

We recommend using [`uv`](https://github.com/astral-sh/uv) or standard `pip` to install the library.

```bash
pip install google-cloud-datastore-odm
```

*(Note: If you are testing locally, ensure you have the Google Cloud Datastore Emulator running and your `DATASTORE_EMULATOR_HOST` environment variable set).*

---

## Step 1: Define a Model

Models represent your Datastore entities. You define them by subclassing `Model` and declaring `Property` descriptors as class attributes.

Let's create a simple `Task` model:

```python
from google_cloud_datastore_odm import Model, StringProperty, BooleanProperty, IntegerProperty

class Task(Model):
    title = StringProperty(required=True)
    description = StringProperty()
    priority = IntegerProperty(default=1, choices=[1, 2, 3, 4, 5])
    is_completed = BooleanProperty(default=False)
```

By default, the Datastore **Kind** will automatically match the name of your class (in this case, `"Task"`).

---

## Step 2: Connect and Save

The ODM automatically connects to Datastore using your environment's default credentials (like the `GOOGLE_CLOUD_PROJECT` variable). You don't need to manually pass connection objects around.

Let's create a task and save it:

```python
# 1. Create an instance in memory
task = Task(title="Write Documentation", description="Draft the getting started guide.", priority=5)

# 2. Save it to Datastore (This automatically generates a unique ID!)
saved_key = task.put()

print(f"Task saved with ID: {saved_key.id_or_name}")
```

Want to specify your own ID instead of letting Datastore generate one? Just pass the `id` argument during creation:

```python
custom_task = Task(id="task-admin-123", title="Review PRs")
custom_task.put()
```

---

## Step 3: Retrieve Data

You can fetch entities directly if you know their Key or their ID.

```python
# Fetch by string or integer ID
fetched_task = Task.get_by_id("task-admin-123")

if fetched_task:
    print(f"Found task: {fetched_task.title}")
    
    # You can access properties via attributes...
    print(f"Completed? {fetched_task.is_completed}")
    
    # ...or like a dictionary!
    print(f"Priority: {fetched_task['priority']}")
```

---

## Step 4: Update and Delete

Updating an entity is as simple as changing its properties in memory and calling `.put()` again. 

```python
# Mark the task as completed
fetched_task.is_completed = True
fetched_task.put()
```

To permanently remove the entity from Datastore:

```python
fetched_task.delete()
```

---

## Step 5: Querying

The ODM features a powerful, Python-native query builder. Let's find all high-priority tasks that are not yet completed:

```python
# 1. Build the query using standard Python operators
high_priority_query = Task.query().filter(
    Task.priority >= 4,
    Task.is_completed == False
)

# 2. Execute and iterate over the results
for open_task in high_priority_query.fetch():
    print(f"URGENT: {open_task.title}")
```

*(Note: Datastore requires composite indexes for complex queries. If you run a query against multiple properties and the index doesn't exist, the Google Cloud SDK will provide a URL in your console output to automatically build it for you).*

---

## Next Steps

You now know the basics! To unlock the true power of the ODM, check out the detailed guides:

* Learn how to structure complex data in the **[Models & Properties](guide/models.md)** guide.
* Enforce data integrity in the **[Validation & Hooks](guide/validation.md)** guide.
* Safely handle concurrent updates in the **[Transactions](guide/transactions.md)** guide.
