import os
from src.google_cloud_datastore_odm import Model, StringField, IntegerField

os.environ['DATASTORE_EMULATOR_HOST'] = 'localhost:20000'
os.environ['GOOGLE_CLOUD_PROJECT'] = 'google-cloud-datastore-odm-dev'


class ExampleModel(Model):
    hey = StringField()
    wow = IntegerField()
    a = IntegerField()


a = ExampleModel(hey="str", wow=4, a=3)

print(a)

stored = a.put()
print(stored.key)

b = ExampleModel.get(key=stored.key)
print(b)
