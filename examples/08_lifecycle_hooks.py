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


class TrackedTask(Model):
    description = StringProperty()

    def _pre_put_hook(self):
        print(f"  [_pre_put] Preparing to save task: {self.description}")

    def _post_put_hook(self):
        print(f"  [_post_put] Successfully saved task with ID: {self.key.id_or_name}")

    @classmethod
    def _pre_get_hook(cls, key):
        print(f"  [_pre_get] Preparing to fetch key: {key.id_or_name}")

    @classmethod
    def _post_get_hook(cls, key, instance):
        print(f"  [_post_get] Fetched key: {key.id_or_name}. Found instance? {instance is not None}")

    @classmethod
    def _pre_delete_hook(cls, key):
        print(f"  [_pre_delete] Preparing to delete key: {key.id_or_name}")

    @classmethod
    def _post_delete_hook(cls, key):
        print(f"  [_post_delete] Successfully deleted key: {key.id_or_name}")


print("--- Triggering Put Hooks ---")
task = TrackedTask(description="Learn Python ODM Hooks")
task_key = task.put()

print("\n--- Triggering Get Hooks ---")
fetched_task = TrackedTask.get(task_key)

print("\n--- Triggering Delete Hooks ---")
fetched_task.delete()
