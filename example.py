from src.google_cloud_datastore_odm import Model, StringField, IntegerField
from dotenv import load_dotenv

load_dotenv()


class ExampleModel(Model):
    name = StringField()
    age = IntegerField()
    score = IntegerField()


example = ExampleModel(name="str", age=4, score=3)

print(f"Example model instance: {example}")

stored_example = example.put()
print(f"Stored example key: {stored_example.key}")

retrieved_example = ExampleModel.get(key=stored_example.key)
print(f"Retrieved example: {retrieved_example}")
