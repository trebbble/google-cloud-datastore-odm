import logging
import os
from time import sleep

import pytest
import requests

from src.google_cloud_datastore_odm.client import get_client
from src.google_cloud_datastore_odm.model import Model
from src.google_cloud_datastore_odm.properties import IntegerProperty, StringProperty


@pytest.fixture(autouse=True, scope="session")
def wait_for_datastore_emulator_ready():
    second = 5
    health_check_endpoint = f"http://{os.environ.get('DATASTORE_EMULATOR_HOST')}/"

    try:
        response = requests.get(health_check_endpoint)
    except Exception:
        response = None

    while not response or response.status_code != 200:
        try:
            logging.info(f"Datastore emulator not ready yet, checking again in {second} seconds")
            sleep(second)
            response = requests.get(health_check_endpoint)
        except Exception:
            response = None


@pytest.fixture(scope="session")
def datastore_client():
    """
    Shared Datastore client for all tests.
    """
    return get_client()


@pytest.fixture
def reset_datastore():
    """
    Reset the Datastore emulator before a test.
    """
    response = requests.post(f"http://{os.environ.get('DATASTORE_EMULATOR_HOST')}/reset")
    assert response.status_code == 200


class Constants:
    STRING_DEFAULT = 'default'
    INTEGER_DEFAULT = 0
    STRING_FIXTURE = 'test'
    INTEGER_FIXTURE = 1


class DummyTestModel(Model):
    __kind__ = "DummyTestModel"
    test_string_field = StringProperty(required=True, default=Constants.STRING_DEFAULT)
    test_integer_field = IntegerProperty(required=True, default=Constants.INTEGER_DEFAULT)


class QueryTestModel(Model):
    __kind__ = "QueryTestModel"
    name = StringProperty()
    age = IntegerProperty()


@pytest.fixture
def sample_dummy_doc() -> DummyTestModel:
    return DummyTestModel(
        test_string_field=Constants.STRING_FIXTURE, 
        test_integer_field=Constants.INTEGER_FIXTURE
    )


@pytest.fixture
def query_model_instance() -> QueryTestModel:
    return QueryTestModel(name="Bob", age=30)
