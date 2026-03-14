"""
Example demonstrating the full public API of google-cloud-datastore-odm.

To run this locally, you need:
  - Datastore emulator running: docker compose -f docker-compose.yml up -d --build
  - A .env file with: DATASTORE_EMULATOR_HOST=localhost:10000 and GOOGLE_CLOUD_PROJECT=google-cloud-datastore-odm-dev
"""

from dotenv import load_dotenv

from src.google_cloud_datastore_odm import IntegerProperty, Model, StringProperty
from src.google_cloud_datastore_odm.model import field_validator, model_validator

load_dotenv()


# ---------------------------------------------------------------------------
# 1. Model Definition
#    - Use __kind__ to customize the Datastore kind (defaults to class name).
#    - Properties enforce Python types and required states.
#    - Use required=True to enforce presence, default= for fallback values.
# ---------------------------------------------------------------------------

class Article(Model):
    __kind__ = "Article"

    title = StringProperty(required=True)
    author = StringProperty(required=True)
    status = StringProperty(default="draft")
    word_count = IntegerProperty(default=0)
    rating = IntegerProperty()

    # -----------------------------------------------------------------------
    # 2. Field-level validators
    #    - Decorated with @field_validator('property_name').
    #    - Run automatically during property assignment.
    #    - Useful for length checks, choices, and numeric bounds.
    # -----------------------------------------------------------------------

    @field_validator('title')
    def validate_title(self, value: str) -> str:
        if len(value) < 3 or len(value) > 200:
            raise ValueError("Title must be between 3 and 200 characters.")
        return value

    @field_validator('status')
    def validate_status(self, value: str) -> str:
        valid_statuses = ["draft", "published", "archived"]
        if value not in valid_statuses:
            raise ValueError(f"Status must be one of {valid_statuses}")
        return value

    @field_validator('word_count')
    def validate_word_count(self, value: int) -> int:
        if value < 0:
            raise ValueError("Word count cannot be negative.")
        return value

    @field_validator('rating')
    def validate_rating(self, value: int) -> int:
        if value not in [1, 2, 3, 4, 5]:
            raise ValueError("Rating must be an integer between 1 and 5.")
        return value

    # -----------------------------------------------------------------------
    # 3. Model-level validators
    #    - Decorated with @model_validator.
    #    - Run when .validate() or .put() is called.
    #    - Used for cross-property logic (e.g., status depends on word_count).
    # -----------------------------------------------------------------------

    @model_validator
    def validate_published_requires_content(self):
        if self.status == "published" and (self.word_count or 0) == 0:
            raise ValueError("A published article must have a word count > 0")


# ---------------------------------------------------------------------------
# 4. Custom property validators (Inline)
#    - Passed as a list to Property(validators=[...]).
#    - Run *before* the @field_validators.
# ---------------------------------------------------------------------------

def no_emoji_allowed(value: str) -> str:
    for char in value:
        if ord(char) > 127:
            raise ValueError(f"Value '{value}' contains non-ASCII characters (emoji not allowed)")
    return value


class Comment(Model):
    __kind__ = "Comment"

    body = StringProperty(required=True, validators=[no_emoji_allowed])
    score = IntegerProperty(default=0)


# ---------------------------------------------------------------------------
# 5. Instance creation
# ---------------------------------------------------------------------------

print("--- Instance Creation ---")
article = Article(title="Hello, World!", author="Alice", word_count=500)
print(f"Created: {article}")
print(f"Has key: {article.has_key}")
print(f"ID before save: {article.id}")

comment = Comment(body="Great article!", score=5)
print(f"Created comment: {comment}")


# ---------------------------------------------------------------------------
# 6. Dictionary-style access and iteration
# ---------------------------------------------------------------------------

print("\n--- Dict-style and Iteration ---")
print(f"article['title'] = {article['title']}")

article['status'] = "published"
print(f"After dict-style set, status: {article.status}")

print("Iterating over keys:", list(article))
print("items():", dict(article.items()))
print("to_dict():", article.to_dict())


# ---------------------------------------------------------------------------
# 7. Persisting to Datastore (.put)
#    - Runs model-level validators before writing.
#    - Assigns & returns a Datastore key on the instance.
# ---------------------------------------------------------------------------

print("\n--- Persistence ---")
saved_article = article.put()
print(f"Saved article: {saved_article}")
print(f"Key: {saved_article.key}")
print(f"ID: {saved_article.id}")


# ---------------------------------------------------------------------------
# 8. Fetching by key (.get)
# ---------------------------------------------------------------------------

print("\n--- Fetching by Key ---")
fetched = Article.get(key=saved_article.key)
print(f"Fetched: {fetched}")
print(f"Fetched ID: {fetched.id}")


# ---------------------------------------------------------------------------
# 9. Fetching by numeric/string ID (.get_by_id, .key_from_id)
# ---------------------------------------------------------------------------

print("\n--- Get by ID ---")
key_from_id = Article.key_from_id(saved_article.id)
print(f"Constructed key: {key_from_id}")
fetched_by_id = Article.get_by_id(saved_article.id)
print(f"Fetched by ID: {fetched_by_id}")


# ---------------------------------------------------------------------------
# 10. Query passthrough (.query().filter().fetch())
# ---------------------------------------------------------------------------

print("\n--- Queries ---")
Article(title="Tutorial: Python ODM", author="Bob", status="published", word_count=1200).put()
Article(title="Advanced Queries", author="Alice", status="published", word_count=800).put()

results = list(Article.query().filter("author", "=", "Alice").fetch())
print(f"Alice's articles: {len(results)} found")
for r in results:
    print(f"  - {r.title} (status={r.status})")

results = list(
    Article.query()
    .filter("author", "=", "Alice")
    .filter("status", "=", "published")
    .fetch()
)
print(f"Alice's published articles: {len(results)} found")

results = list(Article.query().fetch(limit=2))
print(f"First 2 articles (limited): {len(results)} returned")


# ---------------------------------------------------------------------------
# 11. Explicit key allocation (.allocate_key)
# ---------------------------------------------------------------------------

print("\n--- Key Allocation ---")
draft = Article(title="Unfinished Draft", author="Carol", status="draft", word_count=50)
draft.allocate_key()
print(f"Allocated key before put: {draft.key}")
draft.put()
print(f"After put key: {draft.key}, ID: {draft.id}")


# ---------------------------------------------------------------------------
# 12. Model kind introspection
# ---------------------------------------------------------------------------

print("\n--- Introspection ---")
print(f"Article kind: {Article.kind()}")
print(f"Comment kind: {Comment.kind()}")
print(f"Article properties: {list(Article._properties.keys())}")


# ---------------------------------------------------------------------------
# 13. Validation errors
# ---------------------------------------------------------------------------

print("\n--- Validation Examples ---")
try:
    bad = Article(title="X", author="Dave")  # triggers validate_title field_validator
except ValueError as e:
    print(f"Caught field validation error: {e}")

try:
    bad_comment = Comment(body="Love it! 😊")  # triggers inline validator
except ValueError as e:
    print(f"Caught inline validator error: {e}")

try:
    unpublishable = Article(title="No Content", author="Eve", status="published", word_count=0)
    unpublishable.put()  # triggers model_validator at put time
except ValueError as e:
    print(f"Caught model validator error: {e}")

print("\nDone!")
