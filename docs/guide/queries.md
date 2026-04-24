# Queries & Aggregations

Google Cloud Datastore is a NoSQL database, but the ODM provides a powerful, strongly-typed, and fluent query builder that feels just like a traditional SQL ORM.

You can chain filters, apply sorting, paginate results, and even execute lightning-fast server-side aggregations.

---

## Basic Filtering

To query a model, call the `.query()` class method. You can apply filters using standard Python comparison operators (`==`, `!=`, `<`, `<=`, `>`, `>=`) directly on the class properties.

```python
from google_cloud_datastore_odm import Model, StringProperty, IntegerProperty

class Article(Model):
    title = StringProperty()
    author = StringProperty()
    status = StringProperty()
    score = IntegerProperty()

# Find all published articles
q = Article.query().filter(Article.status == "published")

# Fetch the results
for article in q.fetch():
    print(article.title)
```

Passing multiple arguments to `.filter()` implicitly combines them with an `AND` operator:

```python
# Implicit AND
q = Article.query().filter(
    Article.author == "Alice", 
    Article.score >= 5
)
```

---

## Advanced Logic (AND, OR, IN)

For more complex logic, the ODM provides explicit `AND` and `OR` wrappers, as well as `IN` and `NOT_IN` methods.

*(Note: `AND` / `OR` are aliases for `and_` / `or_`. You can use either depending on your stylistic preference).*

### Explicit AND / OR
```python
from google_cloud_datastore_odm import OR, AND

# Find articles by Alice OR Bob
q1 = Article.query().filter(OR(Article.author == "Alice", Article.author == "Bob"))

# Nested logic: (Published AND Score > 10) OR (Author == Alice)
q2 = Article.query().filter(
    OR(
        AND(Article.status == "published", Article.score > 10),
        Article.author == "Alice"
    )
)
```

### Bitwise Operators (`&`, `|`)
If you prefer a more compact syntax, the ODM supports Python's bitwise operators for chaining filters. **You must wrap each condition in parentheses** due to Python's operator precedence rules!

```python
# Bitwise OR and AND
q = Article.query().filter(
    ((Article.author == "Alice") & (Article.status == "draft")) | (Article.score >= 4)
)
```

### IN and NOT IN
To check if a property matches any value in a list, use the `.IN()` or `.NOT_IN()` methods directly on the property.

```python
# Find articles that are either drafts or archived
q = Article.query().filter(Article.status.IN(["draft", "archived"]))
```

---

## Deep Queries (Embedded Models)

If you use `StructuredProperty` to embed models inside other models, the ODM magically allows you to query those nested properties using standard dot-notation!

```python
from google_cloud_datastore_odm import StructuredProperty

class Address(Model):
    city = StringProperty()

class User(Model):
    location = StructuredProperty(Address)

# Query deeply into the embedded entity
q = User.query().filter(User.location.city == "Athens")
```

---

## Ordering
You can sort results by passing properties to `.order()`. Use the unary minus operator (`-`) to sort in descending order.

```python
# Sort by highest score first, then alphabetically by title
q = Article.query().order(-Article.score, Article.title)
```

## Retrieving Data

### Limit
Fetch first N results:
```python
articles = list(Article.query().filter(Article.status == "published").fetch(limit=5))
```
### Single Results
If you only need the first matching entity, use `.get()`. This is highly optimized as it automatically applies a `limit=1` to the background query.

```python
best_article = Article.query().order(-Article.score).get()
```

### Pagination
For APIs and large datasets, never use `.fetch()` on the whole collection. Use `.fetch_page()` to retrieve chunks of data along with a `start_cursor`.

```python
page_query = Article.query().order(Article.title)

cursor = None
while True:
    # Fetches up to 20 items and returns the next cursor
    page, cursor, has_more = page_query.fetch_page(page_size=20, start_cursor=cursor)
    
    for article in page:
        print(article.title)
        
    if not has_more:
        break
```

---

## Optimizing Costs (Projection & Keys Only)

Google Cloud Datastore bills by the number of entities read. To make queries faster and cheaper, you can limit what data is returned.

### Projection & Distinct
If you only need specific fields, use a Projection query. This returns the entities, but only the requested properties will be populated.

```python
# Only download the authors' names
authors = Article.query().projection(Article.author).fetch()

# Find unique authors only
unique_authors = Article.query().distinct_on(Article.author).fetch()
```

!!! tip "Unindexed Properties"
    You cannot run queries, projections, or distinct operations on properties marked with `indexed=False` (like `TextProperty` or `BytesProperty`). The ODM will issue a `UserWarning` if you attempt to do so, as Datastore will return zero results for unindexed properties stored.

### Keys Only
If you just need to check for existence or are preparing to do a batch delete, use a Keys-Only query. These are significantly cheaper and faster than fetching full entities.

```python
# Returns a list of `datastore.Key` objects instead of Model instances
keys = Article.query().keys_only().fetch()
```

---

## Server-Side Aggregations

The ODM supports lightning-fast server-side aggregations. Instead of downloading thousands of entities to count or sum them in Python, you can ask Google's backend to do the math and return a single result.

```python
from google_cloud_datastore_odm import Model, IntegerProperty

class SaleRecord(Model):
    price = IntegerProperty()

base_query = SaleRecord.query()

# Individual Aggregations
total_sales = base_query.count()
total_revenue = base_query.sum(SaleRecord.price)
avg_price = base_query.avg(SaleRecord.price)
```

### Batch Aggregations
To save on network latency, you can perform multiple aggregations in a **single Datastore RPC call** using the `.aggregate()` method. 

Provide alias keyword arguments mapped to the aggregation operations:

```python
from google_cloud_datastore_odm import Count, Sum, Avg

stats = SaleRecord.query().aggregate(
    total_items=Count(),
    total_revenue=Sum(SaleRecord.price),
    average_price=Avg(SaleRecord.price)
)

print(f"Items: {stats['total_items']}")
print(f"Revenue: ${stats['total_revenue']}")
print(f"Average: ${stats['average_price']}")
```
