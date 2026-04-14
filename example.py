"""
Example demonstrating the full public API of google-cloud-datastore-odm.

To run this locally, you need:
  - Datastore emulator running: docker compose -f docker-compose.yml up -d --build
  - A .env file with: DATASTORE_EMULATOR_HOST=localhost:10000 and GOOGLE_CLOUD_PROJECT=google-cloud-datastore-odm-dev
"""

import datetime
import json

from dotenv import load_dotenv

from src.google_cloud_datastore_odm import (
    AND,
    OR,
    Avg,
    BooleanProperty,
    Count,
    DateProperty,
    DateTimeProperty,
    FloatProperty,
    IntegerProperty,
    JsonProperty,
    Model,
    StringProperty,
    Sum,
    TextProperty,
    TimeProperty,
    and_,
    field_validator,
    model_validator,
    or_,
)

load_dotenv()


# ---------------------------------------------------------------------------
# 1. Model Definition
#    - Meta class: Customizes the Datastore kind, namespace, and project.
#    - required/default: Enforce presence or provide fallback values.
#    - choices: Restricts assignments to a specific list of values.
#    - repeated: Turns the property into a list (defaults to []).
#    - indexed: Excludes massive text blocks from Datastore indexes to save space/money.
#    - name: Maps the Python attribute to a legacy/different Datastore column name.
# ---------------------------------------------------------------------------

class Article(Model):
    title = StringProperty(required=True)
    # Maps 'author' in Python to 'author_name' in Datastore
    author = StringProperty(required=True, name="author_name")

    # Built-in choices validation
    status = StringProperty(default="draft", choices=["draft", "published", "archived"])
    rating = IntegerProperty(choices=[1, 2, 3, 4, 5])

    word_count = IntegerProperty(default=0)

    # Strict boolean and float types
    is_featured = BooleanProperty(default=False)
    score = FloatProperty()

    # Chronological properties with auto-population and timezone awareness
    created_at = DateTimeProperty(auto_now_add=True, tzinfo=datetime.timezone.utc)
    updated_at = DateTimeProperty(auto_now=True, tzinfo=datetime.timezone.utc)
    publish_date = DateProperty()
    publish_time = TimeProperty()

    # Repeated list of strings
    tags = StringProperty(repeated=True)

    # Unindexed string (cannot be filtered on in queries)
    internal_notes = StringProperty(indexed=False)

    # Automatically unindexed by default (safe for >1500 bytes)
    body = TextProperty()

    # Automatically unindexed by default (safe for deep dicts/lists)
    metadata: dict | list = JsonProperty()

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
    body = StringProperty(required=True, validators=[no_emoji_allowed])
    score = IntegerProperty(default=0)


# ---------------------------------------------------------------------------
# 5. Reserved Words and Legacy Aliasing
#    - 'key' is reserved by the ODM for Datastore routing and properties exposure
#    - If a legacy Datastore table has a column literally named "key",
#      use the `name="key"` alias to map it to a safe Python property.
#    Properties 'id' and 'parent' can also be declared. In that case, if one needs to pass a direct ID for
#    the entity to be created, or a parent ancestor, they can do by using the alias prefix '_'
# ---------------------------------------------------------------------------

print("--- Reserved Words and Aliasing ---")
try:
    # This will raise a ValueError immediately at class creation time.
    class BadModel(Model):
        key = StringProperty()
except ValueError as e:
    print(f"Correctly caught reserved word error: {e}")


class LegacyDataModel(Model):
    # This maps the Python attribute `legacy_key` to the Datastore column `key`.
    legacy_key = StringProperty(name='key')
    id = StringProperty()
    parent = StringProperty()


parent_key = LegacyDataModel.key_from_id("parent-1")
legacy_instance = LegacyDataModel(
    _id="datastore-key-123", _parent=parent_key,
    legacy_key="some-key",
    id="my_custom_id",
    parent="my_custom_parent"
)
legacy_instance.put()
print(f"Mapped Legacy Instance: Key ID = {legacy_instance.key.name}, Parent = {legacy_instance.key.parent}")
print(f"Legacy dict data: {json.dumps(legacy_instance.to_dict(), indent=4)}")


# ---------------------------------------------------------------------------
# 6. Instance creation (with explicit 'id' shortcut)
# ---------------------------------------------------------------------------

print("\n--- Instance Creation ---")
# Notice we are using id="..." here to explicitly set the Datastore Key name!
article = Article(
    id="my-first-article",
    title="Hello, World!",
    author="Alicia",
    word_count=500,
    is_featured=True,
    score=98.5,
    publish_date=datetime.date.today(),
    publish_time=datetime.datetime.now(datetime.timezone.utc).time(),
    tags=["python", "odm"],
    internal_notes="Review again tomorrow.",
    body="This is a very large block of text that won't blow up our indexes.",
    metadata={"views": 0, "platforms": ["web", "mobile"]}
)
print(f"Created: {article}")
print(f"Has key: {article.key is not None}")
print(f"Explicit ID: {article.key.id_or_name}")

comment = Comment(body="Great article!", score=5)
print(f"Created comment: {comment}")


# ---------------------------------------------------------------------------
# 7. Dictionary-style access and iteration
# ---------------------------------------------------------------------------

print("\n--- Dict-style and Iteration ---")
print(f"article['title'] = {article['title']}")

article['status'] = "published"
print(f"After dict-style set, status: {article.status}")

print("Iterating over keys:", list(article))
print("items():", dict(article.items()))
# Notice that created_at and updated_at are None here because .put() hasn't fired yet!
print("to_dict() before save:", article.to_dict(include=["title", "created_at", "updated_at"]))


# ---------------------------------------------------------------------------
# 8. Persisting to Datastore (.put)
# ---------------------------------------------------------------------------

print("\n--- Persistence ---")
saved_article_key = article.put()
print(f"Saved article: {article}")
print(f"Key: {saved_article_key}")

# Now created_at and updated_at have been auto-populated by the _prepare_for_put hook!
print(f"Auto-generated created_at: {article.created_at}")
print(f"Auto-generated updated_at: {article.updated_at}")


# ---------------------------------------------------------------------------
# 9. Fetching by key (.get)
# ---------------------------------------------------------------------------

print("\n--- Fetching by Key ---")
fetched = Article.get(key=saved_article_key)
print(f"Fetched: {fetched}")
print(f"Fetched ID: {fetched.key.id_or_name}")
print(f"Fetched Tags (Repeated): {fetched.tags}")
print(f"Fetched Metadata (JSON): {fetched.metadata}")
print(f"Fetched Publish Date: {fetched.publish_date} ({type(fetched.publish_date)})")
print(f"Fetched Publish Time: {fetched.publish_time} ({type(fetched.publish_time)})")


# ---------------------------------------------------------------------------
# 10. Fetching by numeric/string ID (.get_by_id, .key_from_id)
# ---------------------------------------------------------------------------

print("\n--- Get by ID ---")
key_from_id = Article.key_from_id("my-first-article")
print(f"Constructed key: {key_from_id}")
fetched_by_id = Article.get_by_id("my-first-article")
print(f"Fetched by explicit ID: {fetched_by_id}")


# ---------------------------------------------------------------------------
# 11. Equality checks (__eq__)
# ---------------------------------------------------------------------------

print("\n--- Equality ---")
# Because fetched_by_id and article have the exact same Key and underlying data:
print(f"Is 'fetched_by_id' equal to 'article'? {fetched_by_id == article}")

# NDB-strictness: Even with the same key, if memory state changes, they are not equal.
fetched_by_id.title = "A New Title in Memory"
print(f"Are they equal after modifying one's title? {fetched_by_id == article}")

# ---------------------------------------------------------------------------
# 12. Batch Operations (put_multi, get_multi, delete_multi)
# ---------------------------------------------------------------------------

print("\n--- Batch Operations & Deletion ---")
batch_articles = [
    Article(title="Batch Article 1", author="System", word_count=100),
    Article(title="Batch Article 2", author="System", word_count=200),
    Article(title="Batch Article 3", author="System", word_count=300),
]

# put_multi performs a single RPC call
batch_keys = Article.put_multi(batch_articles)
print(f"Saved {len(batch_keys)} articles using put_multi.")

# get_multi retrieves instances in the exact order requested
fetched_batch: list[Article] = Article.get_multi(batch_keys)
print(f"Fetched {len(fetched_batch)} articles using get_multi.")
print(f"First fetched from batch: {fetched_batch[0].title}")

# Single instance delete
first_batch_article = fetched_batch[0]
first_batch_article.delete()
print(f"Deleted single article with ID: {first_batch_article.key.id_or_name}")

# delete_multi performs a single RPC call for the rest
remaining_keys = batch_keys[1:]
Article.delete_multi(remaining_keys)
print(f"Deleted remaining {len(remaining_keys)} articles using delete_multi.")


# ---------------------------------------------------------------------------
# 13. Explicit key allocation (.allocate_key, .allocate_ids)
# ---------------------------------------------------------------------------

print("\n--- Key Allocation ---")
draft = Article(title="Unfinished Draft", author="Carol", status="draft", word_count=50)
print(f"Has complete key before allocation? {draft}")

draft.allocate_key()
print(f"Has complete key after allocation? {draft}")
print(f"Allocated key before put: {draft.key}")
draft_key = draft.put()
print(f"After put key: {draft.key}, Returned key: {draft_key}, ID: {draft.key.id_or_name}")

print("\nAllocating a batch of 5 IDs without creating instances yet:")
reserved_keys = Article.allocate_ids(size=5)
for k in reserved_keys:
    print(f"  - Reserved ID: {k.id}")


# ---------------------------------------------------------------------------
# 14. Model kind introspection
# ---------------------------------------------------------------------------

print("\n--- Introspection ---")
print(f"Article kind: {Article.kind()}")
print(f"Comment kind: {Comment.kind()}")
# Showing the different format options for get_schema
print(f"Article full schema: {json.dumps(Article.get_schema(), indent=2)}")
print(f"Article properties: {Article.get_schema(output_format='properties')}")
print(f"Article named properties: {Article.get_schema(output_format='named_properties')}")
print(f"Article properties aliases: {json.dumps(Article.get_schema(output_format='property_aliases'), indent=2)}")


# ---------------------------------------------------------------------------
# 15. Validation errors
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


# ---------------------------------------------------------------------------
# 16. Lifecycle Hooks
# ---------------------------------------------------------------------------

print("\n--- Lifecycle Hooks ---")


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


print("Creating a task to trigger put hooks...")

task = TrackedTask(description="Learn Python ODM Hooks")
task_key = task.put()

print("\nFetching the task to trigger get hooks...")
fetched_task = TrackedTask.get(task_key)

print("\nDeleting the task to trigger delete hooks...")
fetched_task.delete()


# ---------------------------------------------------------------------------
# 17. Cross-Project Routing & Multi-Tenancy
# ---------------------------------------------------------------------------

print("\n--- Cross-Project & Multi-Tenant Routing ---")


class SystemLog(Model):
    event = StringProperty()
    user_id = StringProperty()

    class Meta:
        kind = "AuditLog"
        project = "central-logging-system"
        database = "db-1"
        namespace = "default-events"


log_default = SystemLog(event="Startup", user_id="system")
log_default.put()
print(f"Saved default log: "
      f"project={log_default.key.project}, "
      f"database={log_default.key.database}, "
      f"namespace={log_default.key.namespace}, "
      f"kind={log_default.key.kind}")
print(log_default)


log_tenant = SystemLog(
    event="Login",
    user_id="alicia",
    project="customer-project-123",
    database="db-2",
    namespace="tenant-b"
)
log_tenant.put()
print(f"Saved ad-hoc log: "
      f"project={log_tenant.key.project}, "
      f"database={log_tenant.key.database}, "
      f"namespace={log_tenant.key.namespace}, "
      f"kind={log_tenant.key.kind}")
print(log_tenant)

central_logs = list(SystemLog.query().filter("event", "=", "Startup").fetch())

print(f"Found {len(central_logs)} startup logs in the central project.")

customer_logs = list(
    SystemLog.query(project="customer-project-123", database='db-2', namespace="tenant-b")
    .filter("user_id", "=", "alicia")
    .fetch()
)
print(f"Found {len(customer_logs)} logs for Alicia in customer-project-123.")


# ---------------------------------------------------------------------------
# 18. Advanced NDB-Style Queries & Aggregations
# ---------------------------------------------------------------------------

print("\n--- 19. Advanced NDB-Style Queries ---")

# Seed specific data for testing our advanced operators
print("Seeding data for advanced queries...")
adv_articles = [
    Article(id="adv1", title="Python 101", author="Alice", status="published", word_count=500,
            tags=["python", "beginner"], score=4.9),
    Article(id="adv2", title="GCP Masterclass", author="Bob", status="published", word_count=3500,
            tags=["gcp", "advanced"], score=4.9),
    Article(id="adv3", title="Draft Notes", author="Alice", status="draft", word_count=150,
            tags=["notes"], score=0.0),
    Article(id="adv4", title="Datastore Deep Dive", author="Charlie", status="published", word_count=5000,
            tags=["gcp", "datastore"], score=5.0),
    Article(id="adv5", title="Old Archived Post", author="Bob", status="archived", word_count=1200,
            tags=["legacy"], score=3.2),
]
Article.put_multi(adv_articles)

# ---------------------------------------------------------
# Explicit and Implicit AND Logic
# ---------------------------------------------------------
print("\nScenario A: Explicit and Implicit AND logic")

print("  [Log] Using implicit AND (multiple arguments in .filter()):")
q_a1 = Article.query().filter(Article.author == "Alice", Article.status == "published")
for art in q_a1.fetch():
    art: Article
    print(f"    -> {art.title} (Author: {art.author}, Status: {art.status})")

print("  [Log] Using uppercase AND() alias (NDB Legacy):")
q_a2 = Article.query().filter(AND(Article.author == "Bob", Article.score >= 4.0))
for art in q_a2.fetch():
    art: Article
    print(f"    -> {art.title} (Author: {art.author}, Score: {art.score})")

print("  [Log] Using lowercase and_() method (PEP 8 Compliant):")
q_a3 = Article.query().filter(and_(Article.author == "Charlie", Article.word_count > 1000))
for art in q_a3.fetch():
    art: Article
    print(f"    -> {art.title} (Author: {art.author}, Words: {art.word_count})")


# ---------------------------------------------------------
# Composite OR logic variations
# ---------------------------------------------------------
print("\nScenario B: Composite OR Queries")

print("  [Log] Using uppercase OR() alias (NDB Legacy):")
q_b1 = Article.query().filter(OR(Article.author == "Charlie", Article.score >= 4.5))
for art in q_b1.fetch():
    print(f"    -> {art.title} (Author: {art.author}, Score: {art.score})")

print("  [Log] Using lowercase or_() method (PEP 8 Compliant):")
q_b2 = Article.query().filter(or_(Article.status == "draft", Article.status == "archived"))
for art in q_b2.fetch():
    print(f"    -> {art.title} (Status: {art.status})")

print("\n  [Log] Testing OR with a repeated property (array-membership inside OR):")
# This is the query that crashed the old emulator!
q_b3 = Article.query().filter(OR(Article.author == "Charlie", Article.tags == "beginner"))
for art in q_b3.fetch():
    print(f"    -> {art.title} (Author: {art.author}, Tags: {art.tags})")

# ---------------------------------------------------------
# IN and NOT IN operators (Native)
# ---------------------------------------------------------
print("\nScenario C: IN and NOT IN operators")

print("  [Log] Using lowercase .in_() method (PEP 8 Compliant):")
q_c1 = Article.query().filter(Article.status.in_(["draft", "archived"]))
for art in q_c1.fetch():
    print(f"    -> {art.title} (Status: {art.status})")

print("  [Log] Using uppercase .IN() alias (NDB Legacy):")
q_c2 = Article.query().filter(Article.author.IN(["Alice", "Charlie"]))
for art in q_c2.fetch():
    print(f"    -> {art.title} (Author: {art.author})")

print("  [Log] Using lowercase .not_in_() method (PEP 8 Compliant):")
q_c3 = Article.query().filter(Article.status.not_in_(["published"]))
for art in q_c3.fetch():
    print(f"    -> {art.title} (Status: {art.status})")

print("  [Log] Using uppercase .NOT_IN() alias (NDB Legacy):")
q_c4 = Article.query().filter(Article.author.NOT_IN(["Alice", "Bob"]))
for art in q_c4.fetch():
    print(f"    -> {art.title} (Author: {art.author})")

print("\n  [Log] Testing .in_() on a repeated property (array-contains-any):")
q_c5 = Article.query().filter(Article.tags.in_(["notes", "datastore"]))
for art in q_c5.fetch():
    print(f"    -> {art.title} (Tags: {art.tags})")

# ---------------------------------------------------------
# Bitwise logical operators (& and |)
# ---------------------------------------------------------
print("\nScenario D: Bitwise Logical Operators (&, |)")
print("  [Log] Using Python bitwise operators for clean syntax:")
# Note: Python requires parenthesis around conditions when using bitwise operators!
q_d = Article.query().filter(
    ((Article.author == "Alice") & (Article.status == "draft")) | (Article.score >= 4.9)
)
for art in q_d.fetch():
    print(f"    -> {art.title} (Author: {art.author}, Status: {art.status}, Score: {art.score})")


# ---------------------------------------------------------
# Advanced Ordering (Descending and Ascending)
# ---------------------------------------------------------
print("\nScenario E: Sorting / Ordering (-/+)")
print("  [Log] Sorting by descending score (-), then ascending title:")
q_e = Article.query().order(-Article.score, Article.title)
for art in q_e.fetch():
    print(f"    -> {art.title} (Score: {art.score})")

print("  [Log] Sorting published by descending score (-), then ascending title:")
q_e2 = Article.query().filter(Article.status == "published").order(-Article.score, Article.title)
for art in q_e2.fetch():
    print(f"    -> {art.title} (Score: {art.score})")


# ---------------------------------------------------------
# Server-Side Aggregation (Count)
# ---------------------------------------------------------
print("\nServer-Side Aggregations")
base_query = Article.query().filter(Article.status == "published")

total_published = base_query.count()
total_words = base_query.sum(Article.word_count)
average_words = base_query.avg(Article.word_count)

print(f"Total published articles: {total_published}")
print(f"Total Words Written: {total_words}")
print(f"Average Words per Article: {average_words:.1f}")

print("\n--- Batch Aggregations ---")
stats = base_query.aggregate(
    total_articles=Count(),
    total_words=Sum(Article.word_count),
    average_words=Avg('word_count')
)

print(f"Total Published Articles: {stats['total_articles']}")
print(f"Total Words Written: {stats['total_words']}")
print(f"Average Words per Article: {stats['average_words']:.1f}")
# ---------------------------------------------------------
# Passthrough queries
# ---------------------------------------------------------
print("\nScenario G: Passthrough queries")
results: list[Article] = list(Article.query().filter("author_name", "=", "Alice").fetch())
print(f"Alice's articles: {len(results)} found")
for r in results:
    r: Article
    print(f"  - {r.title} (status={r.status}, tags={r.tags})")


# ---------------------------------------------------------
# Get first or none
# ---------------------------------------------------------

# The classic Query.get() - Returns the first draft it finds or None
print("\nGet on query to fetch first or none:")
first_draft = Article.query().filter(Article.status == "draft").get()
print(f"First draft: {first_draft}")
non_existing_status = Article.query().filter(Article.status == "dummy").get()
print(f"Wrong status: {non_existing_status}")

# ---------------------------------------------------------
# Distinct
# ---------------------------------------------------------

unique_authors = list(Article.query().distinct_on(Article.author).fetch())
print(f"\nUnique authors: {len(unique_authors)} found")
for r in unique_authors:
    r: Article
    print(f"- {r.author}")

# ---------------------------------------------------------
# Projection
# ---------------------------------------------------------
just_authors = list(Article.query().projection(Article.author).fetch())
print(f"\nAll authors: {len(unique_authors)} found")
for r in just_authors:
    r: Article
    print(f"- {r}")

try:
    print(unique_authors[0].title)
except AttributeError as e:
    print(e)

# ---------------------------------------------------------
# Projection & Distinct
# ---------------------------------------------------------
unique_authors = list(Article.query().projection(Article.author, 'title').distinct_on(Article.author).fetch())
print(f"\nUnique authors with titles: {len(unique_authors)} found")
for r in unique_authors:
    r: Article
    print(f"- {r}")

# ---------------------------------------------------------
# Keys Only Fetching - Super fast, doesn't download document payloads
# ---------------------------------------------------------
all_keys = list(Article.query().keys_only().fetch())
print(f"\nFound {len(all_keys)} keys")

# ---------------------------------------------------------
# --- Pagination / Cursors ---
# ---------------------------------------------------------
print("\n--- Pagination / Cursors ---")

query = (
    Article.query()
    .order(Article.author)
    .projection(Article.author, Article.title)
    .distinct_on(Article.author)
)

cursor = None
has_more = True

while has_more:
    page, cursor, has_more = query.fetch_page(page_size=2, start_cursor=cursor)

    for article in page:
        print(f"{article.author} - {article.title}")

print("\nExample Run Complete!")
