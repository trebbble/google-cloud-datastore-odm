from src.google_cloud_datastore_odm.model import Model
from src.google_cloud_datastore_odm.properties import IntegerProperty, StringProperty


class Article(Model):
    title = StringProperty(required=True)
    views = IntegerProperty(default=0)


def test_public_api_usage(reset_datastore):
    article = Article(title="Hello World")

    article.put()
    assert article.key is not None
    assert article.id is not None

    assert article.title == "Hello World"
    assert article.views == 0
    assert article["title"] == "Hello World"
    assert article["views"] == 0

    # Attribute access
    article.title = "Changed"
    article.views = 1
    article.put()

    assert article.title == "Changed"
    assert article.views == 1
    assert article["title"] == "Changed"
    assert article["views"] == 1

    # Dict-style access
    article["title"] = "Changed again"
    article["views"] = 2
    article.put()

    assert article.title == "Changed again"
    assert article.views == 2
    assert article["title"] == "Changed again"
    assert article["views"] == 2

    # Fetch
    fetched = Article.get(article.key)
    assert fetched.title == "Changed again"
    assert fetched.views == 2
    assert fetched["title"] == "Changed again"
    assert fetched["views"] == 2

    # Query
    results = list(Article.query().filter("views", "=", 2).fetch())
    assert len(results) == 1
