"""
Example demonstrating the full public API of google-cloud-datastore-odm.

To run this locally, you need:
  - Datastore emulator running: docker compose -f docker-compose.yml up -d --build
  - A .env file with: DATASTORE_EMULATOR_HOST=localhost:10000 and GOOGLE_CLOUD_PROJECT=google-cloud-datastore-odm-dev
"""

import json

from dotenv import load_dotenv

from src.google_cloud_datastore_odm import IntegerProperty, Model, StringProperty
from src.google_cloud_datastore_odm.model import field_validator, model_validator

load_dotenv()


# ---------------------------------------------------------------------------
# 1. Model Definition
#    - __kind__: Customizes the Datastore kind (defaults to class name).
#    - required/default: Enforce presence or provide fallback values.
#    - choices: Restricts assignments to a specific list of values.
#    - repeated: Turns the property into a list (defaults to []).
#    - indexed: Excludes massive text blocks from Datastore indexes to save space/money.
#    - name: Maps the Python attribute to a legacy/different Datastore column name.
# ---------------------------------------------------------------------------

class Article(Model):
    __kind__ = "Article"

    title = StringProperty(required=True)
    # Maps 'author' in Python to 'author_name' in Datastore
    author = StringProperty(required=True, name="author_name")

    # Built-in choices validation
    status = StringProperty(default="draft", choices=["draft", "published", "archived"])
    rating = IntegerProperty(choices=[1, 2, 3, 4, 5])

    word_count = IntegerProperty(default=0)

    # Repeated list of strings
    tags = StringProperty(repeated=True)

    # Unindexed property (cannot be filtered on in queries)
    internal_notes = StringProperty(indexed=False)

    # -----------------------------------------------------------------------
    # 2. Field-level validators
    #    - Decorated with @field_validator('property_name').
    #    - Run automatically during property assignment.
    # -----------------------------------------------------------------------

    @field_validator('title')
    def validate_title(self, value: str) -> str:
        if len(value) < 3 or len(value) > 200:
            raise ValueError("Title must be between 3 and 200 characters.")
        return value

    @field_validator('word_count')
    def validate_word_count(self, value: int) -> int:
        if value < 0:
            raise ValueError("Word count cannot be negative.")
        return value

    # -----------------------------------------------------------------------
    # 3. Model-level validators
    #    - Decorated with @model_validator.
    #    - Run when .validate() or .put() is called.
    #    - Used for cross-property logic.
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
# 5. Instance creation (with explicit 'id' shortcut)
# ---------------------------------------------------------------------------

print("--- Instance Creation ---")
# Notice we are using id="..." here to explicitly set the Datastore Key name!
article = Article(
    id="my-first-article",
    title="Hello, World!",
    author="Alice",
    word_count=500,
    tags=["python", "odm"],
    internal_notes="Review again tomorrow."
)
print(f"Created: {article}")
print(f"Has key: {article.has_key}")
print(f"Explicit ID: {article.id}")

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
# ---------------------------------------------------------------------------

print("\n--- Persistence ---")
saved_article = article.put()
print(f"Saved article: {saved_article}")
print(f"Key: {saved_article.key}")


# ---------------------------------------------------------------------------
# 8. Fetching by key (.get)
# ---------------------------------------------------------------------------

print("\n--- Fetching by Key ---")
fetched = Article.get(key=saved_article.key)
print(f"Fetched: {fetched}")
print(f"Fetched ID: {fetched.id}")
print(f"Fetched Tags (Repeated): {fetched.tags}")


# ---------------------------------------------------------------------------
# 9. Fetching by numeric/string ID (.get_by_id, .key_from_id)
# ---------------------------------------------------------------------------

print("\n--- Get by ID ---")
key_from_id = Article.key_from_id("my-first-article")
print(f"Constructed key: {key_from_id}")
fetched_by_id = Article.get_by_id("my-first-article")
print(f"Fetched by explicit ID: {fetched_by_id}")


# ---------------------------------------------------------------------------
# 10. Query passthrough (.query().filter().fetch())
# ---------------------------------------------------------------------------

print("\n--- Queries ---")
Article(title="Tutorial: Python ODM", author="Bob", status="published", word_count=1200, tags=["tutorial"]).put()
Article(title="Advanced Queries", author="Alice", status="published", word_count=800, tags=["advanced"]).put()

# Note: Datastore filters use the Datastore alias name under the hood,
# but for now we filter using the mapped names.
results: list[Article] = list(Article.query().filter("author_name", "=", "Alice").fetch())
print(f"Alice's articles: {len(results)} found")
for r in results:
    # Adding an explicit type hint to satisfy PyCharm's static analyzer
    r: Article
    print(f"  - {r.title} (status={r.status}, tags={r.tags})")

results_limited: list[Article] = list(Article.query().fetch(limit=2))
print(f"First 2 articles (limited): {len(results_limited)} returned")


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
print(f"Article full schema: {json.dumps(Article.get_schema(), indent=2)}")
print(f"Article properties: {Article.get_schema(output_format='properties')}")
print(f"Article named properties: {Article.get_schema(output_format='named_properties')}")
print(f"Article properties aliases: {json.dumps(Article.get_schema(output_format='property_aliases'), indent=2)}")

# ---------------------------------------------------------------------------
# 13. Validation errors
# ---------------------------------------------------------------------------

print("\n--- Validation Examples ---")
try:
    bad = Article(title="X", author="Dave")  # triggers validate_title field_validator
except ValueError as e:
    print(f"Caught field validation error: {e}")

try:
    bad_choice = Article(title="Test", author="Dave", status="deleted")  # 'deleted' not in choices
except ValueError as e:
    print(f"Caught built-in choice error: {e}")

try:
    bad_list = Article(title="Test", author="Dave", tags="not-a-list")  # passing string to repeated
except TypeError as e:
    print(f"Caught repeated property type error: {e}")

try:
    unpublishable = Article(title="No Content", author="Eve", status="published", word_count=0)
    unpublishable.put()  # triggers model_validator at put time
except ValueError as e:
    print(f"Caught model validator error: {e}")

print("\nDone!")
