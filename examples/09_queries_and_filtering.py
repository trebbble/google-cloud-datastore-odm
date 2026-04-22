"""
To run this locally:
  - Emulator: docker compose -f docker-compose.yml up -d --build
  - Env: DATASTORE_EMULATOR_HOST=localhost:10000 and GOOGLE_CLOUD_PROJECT=google-cloud-datastore-odm-dev
"""

from pathlib import Path

from dotenv import load_dotenv

from google_cloud_datastore_odm import AND, OR, IntegerProperty, Model, StringProperty, StructuredProperty, and_, or_

load_dotenv()
print("\n" + "=" * 60)
print(f"Running: {Path(__file__).name}")
print("=" * 60 + "\n")


class Address(Model):
    city = StringProperty()


class Article(Model):
    title = StringProperty()
    author = StringProperty()
    status = StringProperty()
    score = IntegerProperty()
    tags = StringProperty(repeated=True)
    location = StructuredProperty(Address)
    internal_notes = StringProperty(indexed=False)


print("--- Seeding Data ---")
Article.put_multi([
    Article(id="adv1", title="Python 101", author="Alice", status="published", score=5, tags=["python"],
            location=Address(city="London")),
    Article(id="adv2", title="GCP Pro", author="Bob", status="published", score=4, tags=["gcp"],
            location=Address(city="Athens")),
    Article(id="adv3", title="Draft Notes", author="Alice", status="draft", score=0, tags=["notes"]),
    Article(id="adv4", title="Archived", author="Bob", status="archived", score=3, tags=["legacy"]),
])

print("\n--- Implicit & Explicit AND/and_ ---")
q1 = Article.query().filter(Article.author == "Alice", Article.status == "published")
print(f"Alice published: {[a.title for a in q1.fetch()]}")

q11 = Article.query().filter(and_(Article.author == "Alice", Article.status == "published"))
print(f"Alice published: {[a.title for a in q11.fetch()]}")

q12 = Article.query().filter(AND(Article.author == "Alice", Article.status == "published"))
print(f"Alice published: {[a.title for a in q12.fetch()]}")

print("\n---  OR/or_ ---")
q2 = Article.query().filter(OR(Article.tags == "python", Article.tags == "gcp"))
print(f"Python OR GCP tags: {[a.title for a in q2.fetch()]}")

q21 = Article.query().filter(or_(Article.tags == "python", Article.tags == "gcp"))
print(f"Python OR GCP tags: {[a.title for a in q21.fetch()]}")

print("\n--- Bitwise Operators (&, |) ---")
q3 = Article.query().filter(((Article.author == "Alice") & (Article.status == "draft")) | (Article.score >= 4))
print(f"Alice Drafts OR High Score: {[a.title for a in q3.fetch()]}")

print("\n--- Native IN/in_ and NOT_IN/not_in_ ---")
q4 = Article.query().filter(Article.status.in_(["draft", "archived"]))
print(f"Status in (draft, archived): {[a.title for a in q4.fetch()]}")

q41 = Article.query().filter(Article.status.IN(["draft", "archived"]))
print(f"Status in (draft, archived): {[a.title for a in q41.fetch()]}")

q42 = Article.query().filter(Article.status.NOT_IN(["draft", "archived"]))
print(f"Status not in (draft, archived): {[a.title for a in q42.fetch()]}")

q43 = Article.query().filter(Article.status.not_in_(["draft", "archived"]))
print(f"Status not in (draft, archived): {[a.title for a in q43.fetch()]}")

print("\n--- Embedded / Deep Queries ---")
q5 = Article.query().filter(Article.location.city == "Athens")
print(f"Articles from Athens: {[a.title for a in q5.fetch()]}")

print("\n--- Sorting / Ordering ---")
q6 = Article.query().order(-Article.score, Article.title)
print(f"Highest score first then ascending title: {[(a.title, a.score) for a in q6.fetch()]}")

print("\n--- Projection ---")
only_authors = list(Article.query().projection(Article.author).fetch())
print(f"Only authors: {[a for a in only_authors]}")

print("\n---  Distinct ---")
unique_authors = list(Article.query().distinct_on(Article.author).fetch())
print(f"Unique authors: {[a for a in unique_authors]}")

print("\n--- Projection & Distinct ---")
unique_authors_with_titles = list(
    Article.query().projection(Article.author, 'title').distinct_on(Article.author).fetch()
)
print(f"Unique authors with titles: {[a for a in unique_authors_with_titles]}")

print("\n--- Keys Only ---")
keys = list(Article.query().keys_only().fetch())
print(f"Fetched {len(keys)} keys instantly.")

print("\n--- Get first or None ---")
highest_published_score = Article.query().filter(Article.status == "published").order(-Article.score).get()
print(f"Highest score and published: {highest_published_score}")

print("\n--- Cursor Pagination ---")
page_query = Article.query().order(Article.title)
cursor = None
for i in range(1, 3):
    page, cursor, has_more = page_query.fetch_page(page_size=2, start_cursor=cursor)
    print(f"Page {i}: {[a.title for a in page]}")

print("\n--- Raw Passthrough & Warnings ---")
raw_results = list(Article.query().filter("status", "=", "published").fetch())
print(f"Passthrough raw filter found: {len(raw_results)}")

print("[Warning Output Expected Below:]")
list(Article.query().filter(Article.internal_notes != "").fetch())
