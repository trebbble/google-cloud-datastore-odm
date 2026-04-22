"""
To run this locally:
  - Emulator: docker compose -f docker-compose.yml up -d --build
  - Env: DATASTORE_EMULATOR_HOST=localhost:10000 and GOOGLE_CLOUD_PROJECT=google-cloud-datastore-odm-dev
"""

from pathlib import Path
from dotenv import load_dotenv
from google_cloud_datastore_odm import (
    Model, StringProperty, IntegerProperty, field_validator, model_validator
)

load_dotenv()
print("\n" + "=" * 60)
print(f"Running: {Path(__file__).name}")
print("=" * 60 + "\n")


# 1. Inline Property Validators and Field Validators run upon assignment
# 2. In case a field has both inline and field validators then inline run first and field ones second
# 3. Model validators run only right before persistence with .put() or on demand with .validate()

def no_emoji_allowed(value: str) -> str:
    for char in value:
        if ord(char) > 127:
            raise ValueError(f"Value '{value}' contains non-ASCII characters.")
    return value


class ValidatedArticle(Model):
    title = StringProperty(required=True)
    clean_notes = StringProperty(validators=[no_emoji_allowed])
    status = StringProperty(default="draft", choices=["draft", "published"])
    word_count = IntegerProperty(default=0)

    @field_validator("title")
    def validate_title(self, value: str) -> str:
        if len(value) < 3 or len(value) > 200:
            raise ValueError("Title must be between 3 and 200 characters.")
        return value

    @model_validator
    def validate_published_requires_content(self):
        if self.status == "published" and (self.word_count or 0) == 0:
            raise ValueError("A published article must have a word count > 0")


print("--- Testing Property Parameters Validators ---")
try:
    print("[Test] Attempting to assign invalid choice...")
    doc = ValidatedArticle(title="Valid Title", status="deleted")
except ValueError as e:
    print(f"[Caught] Choice Validator Error: {e}")


print("\n--- Testing Property Inline Validators ---")
try:
    print("[Test] Attempting to assign emoji to clean_notes...")
    doc = ValidatedArticle(title="Valid Title", clean_notes="Hello 😊")
except ValueError as e:
    print(f"[Caught] Inline Validator Error: {e}")

print("\n--- Testing Property Field Validators ---")
try:
    print("[Test] Attempting to assign a 1-character title...")
    doc = ValidatedArticle(title="A")
except ValueError as e:
    print(f"[Caught] Field Validator Error: {e}")


print("\n--- Testing Model Validators ---")
try:
    doc = ValidatedArticle(title="Valid Title", status="published", word_count=0)
    print("[Test] Created document in memory (no error yet because model validators run on save).")
    print("[Test] Calling .put()...")
    doc.put()
except ValueError as e:
    print(f"[Caught] Model Validator Error: {e}")
