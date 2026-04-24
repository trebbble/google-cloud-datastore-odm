# Multi-Tenancy & Routing

In modern SaaS applications or enterprise microservices, you often need to partition data. Google Cloud Datastore provides three levels of isolation:

1. **Projects:** The highest level of isolation (completely separate GCP projects).
2. **Databases:** Separate Datastore instances within the same project.
3. **Namespaces:** Logical partitions within the same database (perfect for multi-tenancy).

The ODM allows you to effortlessly route entities and queries to any combination of these three partitions, either globally via a `Meta` class or dynamically on a per-instance basis.

---

## Model-Level Defaults (`Meta`)

If a specific model should *always* be saved to a dedicated project, database, or namespace, you can hardcode these defaults using an inner `Meta` class.

You can also use the `Meta` class to decouple the Python class name from the actual Datastore **Kind** (table name).

```python
from google_cloud_datastore_odm import Model, StringProperty

class SystemLog(Model):
    event = StringProperty()
    user_id = StringProperty()

    class Meta:
        # Override the Datastore Kind (table name)
        kind = "AuditLog"
        
        # Route all SystemLogs to a dedicated GCP project
        project = "central-logging-system"
        
        # Route to a specific named database (instead of '(default)')
        database = "db-1"
        
        # Route to a specific namespace
        namespace = "system-events"

# Saved to: central-logging-system / db-1 / system-events
log = SystemLog(event="Startup", user_id="system")
log.put()
```

If you don't define a `Meta` class, the ODM will simply fall back to the environment variables and default configuration initialized by your Datastore Client.

---

## Dynamic Multi-Tenancy (Instance Overrides)

In a true multi-tenant application, you usually don't want to hardcode the tenant name in the model class. Instead, you determine the tenant dynamically (e.g., from an HTTP request header) and route the data on the fly.

You can override the `Meta` defaults for a specific entity by passing `project`, `database`, or `namespace` directly into the constructor as keyword arguments.

```python
def log_user_action(tenant_id: str, action: str, user: str):
    # Dynamically route this specific entity to the tenant's namespace!
    tenant_log = SystemLog(
        event=action,
        user_id=user,
        namespace=tenant_id,     # Overrides the 'system-events' default
        database="customer-db"   # Overrides the 'db-1' default
    )
    
    # Saved to: central-logging-system / customer-db / <tenant_id>
    tenant_log.put()

# Example usage
log_user_action("tenant-a", "Login", "alice")
log_user_action("tenant-b", "Download", "bob")
```

!!! tip "Total Data Isolation"
    Because these entities are saved in different namespaces or databases, they are completely invisible to each other. A query run in `tenant-a`'s namespace will *never* accidentally return `tenant-b`'s data. This makes GDPR compliance and data deletion incredibly easy!

---

## Query Routing

The `Query` object perfectly mirrors the routing behavior of the Models. 

If you call `.query()` with no arguments, it uses the `Meta` defaults. If you want to query a specific tenant's data, simply pass the routing arguments into the `.query()` method.

```python
# 1. Query the default (Meta) partition
central_logs = SystemLog.query().fetch()

print(f"Found {len(list(central_logs))} logs in the central system.")

# 2. Query a specific tenant's partition
customer_b_logs = SystemLog.query(
    namespace="tenant-b",
    database="customer-db"
).fetch()

for log in customer_b_logs:
    print(f"Tenant B Log: {log.event} by {log.user_id}")
```
