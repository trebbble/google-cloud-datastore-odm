import os
import pytest
import requests
import logging
from time import sleep

from src.google_cloud_datastore_odm.client import get_client


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



