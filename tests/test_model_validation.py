import pytest

from src.google_cloud_datastore_odm.model import Model, model_validator
from src.google_cloud_datastore_odm.fields import StringField, IntegerField


class UserWithValidator(Model):
    name_field = StringField()
    age_field = IntegerField()

    @model_validator
    def validate_age_nonnegative(self):
        if self.age_field < 0:
            raise ValueError("Age cannot be negative")


def test_model_validator_explicit():
    instance = UserWithValidator(name_field="Alice", age_field=10)
    instance.validate()

    instance.age_field = -5
    with pytest.raises(ValueError):
        instance.validate()


def test_multiple_model_validators():
    class Product(Model):
        price_field = IntegerField()
        stock_field = IntegerField()

        @model_validator
        def validate_price(self):
            if self.price_field < 0:
                raise ValueError("Price must be non-negative")

        @model_validator
        def validate_stock(self):
            if self.stock_field < 0:
                raise ValueError("Stock must be non-negative")

    product = Product(price_field=10, stock_field=5)
    product.validate()

    product.price_field = -1
    with pytest.raises(ValueError):
        product.validate()

    product.price_field = 10
    product.stock_field = -2
    with pytest.raises(ValueError):
        product.validate()
