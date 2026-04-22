"""
To run this locally:
  - Emulator: docker compose -f docker-compose.yml up -d --build
  - Env: DATASTORE_EMULATOR_HOST=localhost:10000 and GOOGLE_CLOUD_PROJECT=google-cloud-datastore-odm-dev
"""

from pathlib import Path
from dotenv import load_dotenv
from google_cloud_datastore_odm import Model, StringProperty

load_dotenv()
print("\n" + "=" * 60)
print(f"Running: {Path(__file__).name}")
print("=" * 60 + "\n")


class SystemLog(Model):
    event = StringProperty()
    user_id = StringProperty()

    # Meta class sets the hard defaults for this Model
    class Meta:
        # Overrides the class name 'SystemLog'
        kind = "AuditLog"
        # routes to specific project; potentially different than default pickedup by client
        project = "central-logging-system"
        # routes to specific database; not '(default)'
        database = "db-1"
        # routes to specific namespace; not '(default)'
        namespace = "default-events"


print("--- Default Meta Routing ---")
log_default = SystemLog(event="Startup", user_id="system")
log_default.put()

print(f"[SystemLog] Saved using defaults from Meta config:")
print(f"  - Project: {log_default.key.project}")
print(f"  - Database: {log_default.key.database}")
print(f"  - Namespace: {log_default.key.namespace}")

print("\n--- Ad-hoc Instance Routing (Multi-Tenancy) ---")
# By passing these reserved kwargs, we override the Meta class for this specific instance
log_tenant = SystemLog(
    event="Login",
    user_id="alicia",
    project="customer-project-123",
    database="db-2",
    namespace="tenant-b"
)
log_tenant.put()

print(f"[SystemLog] Saved using explicit kwargs to override ad-hoc:")
print(f"  - Project: {log_tenant.key.project}")
print(f"  - Database: {log_tenant.key.database}")
print(f"  - Namespace: {log_tenant.key.namespace}")

print("\n--- Query Routing using defaults from Meta config ---")
central_logs = list(SystemLog.query().fetch())
print(f"[Query] Found {len(central_logs)} logs in central-logging-system:")
for log in central_logs:
    print(f" ID: {log.key.id_or_name} "
          f"- Project: {log.key.project} "
          f"- Database: {log.key.database} "
          f"- Namespace: {log.key.namespace}")

print("\n--- Query Routing explicit kwargs to override ad-hoc ---")
customer_logs = list(SystemLog.query(project="customer-project-123", database="db-2", namespace="tenant-b").fetch())
print(f"[Query] Found {len(customer_logs)} logs isolated in customer-project-123/tenant-b.")
for log in customer_logs:
    print(f" ID: {log.key.id_or_name} "
          f"- Project: {log.key.project} "
          f"- Database: {log.key.database} "
          f"- Namespace: {log.key.namespace}")
