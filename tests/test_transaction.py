from unittest.mock import MagicMock, patch

import pytest
from google.api_core.exceptions import Aborted
from google.cloud import datastore

from google_cloud_datastore_odm import IntegerProperty, Model, StringProperty, transaction, transactional
from google_cloud_datastore_odm.transaction import get_current_transaction
from tests.conftest import QueryTestModel


class BankAccount(Model):
    owner = StringProperty()
    balance = IntegerProperty()


class AuditLog(Model):
    action = StringProperty()
    amount = IntegerProperty()


class RoutedModel(Model):
    name = StringProperty()

    class Meta:
        project = "custom-txn-project"
        database = "custom-txn-db"
        namespace = "secure-ns"


def test_transaction_context_lifecycle():
    """Ensure the contextvar is correctly set and cleared."""
    assert get_current_transaction() is None

    with transaction():
        txn = get_current_transaction()
        assert txn is not None
        assert isinstance(txn, datastore.Transaction)

    assert get_current_transaction() is None


def test_transaction_nested_rejection():
    """Ensure nested transactions throw a RuntimeError."""
    with pytest.raises(RuntimeError):
        with transaction():
            with transaction():
                pass


def test_transaction_commit(reset_datastore):
    """Ensure successful operations inside a block hit the database."""
    with transaction():
        user = QueryTestModel(name="CommitUser", age=30)
        user.put()

    fetched: QueryTestModel = QueryTestModel.query().filter(QueryTestModel.name == "CommitUser").get()
    assert fetched is not None
    assert fetched.age == 30

    with transaction():
        refetched = QueryTestModel.get(fetched.key)
        refetched.delete()

    refetched: QueryTestModel = QueryTestModel.query().filter(QueryTestModel.name == "CommitUser").get()
    assert refetched is None


def test_transaction_rollback_on_error(reset_datastore):
    """Ensure an exception rolls back all queued database mutations."""
    try:
        with transaction():
            user = QueryTestModel(name="RollbackUser", age=99)
            user.put()
            raise ValueError("Simulated business logic crash!")
    except ValueError:
        pass

    fetched = QueryTestModel.query().filter(QueryTestModel.name == "RollbackUser").get()
    assert fetched is None


def test_transaction_batch_routing(reset_datastore):
    """Ensure multi operations are correctly buffered in the transaction."""
    user1 = QueryTestModel(name="BatchUser1", age=1)
    user2 = QueryTestModel(name="BatchUser2", age=2)

    with transaction():
        keys = QueryTestModel.put_multi([user1, user2])

        fetched = QueryTestModel.get_multi(keys)
        assert len(fetched) == 2

        QueryTestModel.delete_multi(keys)

    assert QueryTestModel.get(keys[0]) is None


def test_transactional_generator_ban():
    """Ensure the decorator actively refuses to wrap generator functions."""
    with pytest.raises(TypeError):

        @transactional()
        def bad_generator_txn():
            yield 1


@patch("src.google_cloud_datastore_odm.transaction.time.sleep")
def test_transactional_retry_success(mock_sleep, reset_datastore):
    """Ensure the decorator retries on Aborted and eventually succeeds."""
    attempt_tracker = {"count": 0}

    @transactional(retries=3)
    def flaky_transfer():
        attempt_tracker["count"] += 1

        if attempt_tracker["count"] <= 2:
            raise Aborted("Simulated Concurrency Conflict")

        user = QueryTestModel(name="RetryUser", age=50)
        user.put()
        return "Success"

    result = flaky_transfer()

    assert result == "Success"
    assert attempt_tracker["count"] == 3

    assert mock_sleep.call_count == 2

    assert QueryTestModel.query().filter(QueryTestModel.name == "RetryUser").get() is not None


@patch("src.google_cloud_datastore_odm.transaction.time.sleep")
def test_transactional_retry_exhaustion(mock_sleep):
    """Ensure the decorator gives up and raises the exception after max retries."""
    mock_func = MagicMock(side_effect=Aborted("Constant Collision"))

    decorated_func = transactional(retries=2)(mock_func)

    with pytest.raises(Aborted, match="Constant Collision"):
        decorated_func()

    assert mock_func.call_count == 3
    assert mock_sleep.call_count == 2


def test_transaction_multi_model_coordination(reset_datastore):
    """Ensure multiple different models can be modified in a single transaction."""
    acc1 = BankAccount(owner="Alice", balance=100)
    acc2 = BankAccount(owner="Bob", balance=50)
    acc1.put()
    acc2.put()

    with transaction():
        a = BankAccount.get(acc1.key)
        b = BankAccount.get(acc2.key)

        a.balance -= 30
        b.balance += 30

        log = AuditLog(action="Transfer: Alice to Bob", amount=30)

        a.put()
        b.put()
        log.put()

    assert BankAccount.get(acc1.key).balance == 70
    assert BankAccount.get(acc2.key).balance == 80

    logs = list(AuditLog.query().fetch())
    assert len(logs) == 1
    assert logs[0].action == "Transfer: Alice to Bob"


def test_transaction_routing_arguments():
    """Ensure the transaction context manager correctly passes routing args to the Client."""

    with transaction(project="test-proj", database="test-db"):
        log = AuditLog(action="Transfer: Alice to Bob", amount=30)
        log.put()

    default_logs = list(AuditLog.query().fetch())
    assert len(default_logs) == 0

    logs = list(AuditLog.query(project="test-proj", database="test-db").fetch())
    assert len(logs) == 1
    assert logs[0].action == "Transfer: Alice to Bob"


def test_transaction_namespace_isolation(reset_datastore):
    """Ensure transactions respect namespace boundaries for allocations and mutations."""
    with transaction(project="custom-txn-project", database="custom-txn-db"):
        r1 = RoutedModel(name="Secret 1")
        r2 = RoutedModel(name="Secret 2")
        RoutedModel.put_multi([r1, r2])

    default_results = list(RoutedModel.query(namespace="default").fetch())
    assert len(default_results) == 0

    secure_results = list(RoutedModel.query(namespace="secure-ns").fetch())
    assert len(secure_results) == 2
    assert secure_results[0].key.namespace == "secure-ns"
    assert secure_results[0].key.project == "custom-txn-project"


def test_transaction_bound_queries(reset_datastore):
    """Ensure queries executed inside a transaction see the exact database snapshot."""
    from tests.conftest import QueryTestModel

    user1 = QueryTestModel(name="Alice", age=20)
    user2 = QueryTestModel(name="Bob", age=30)
    QueryTestModel.put_multi([user1, user2])

    with transaction():
        results = list(QueryTestModel.query().filter(QueryTestModel.age >= 20).fetch())
        assert len(results) == 2

        QueryTestModel(name="Charlie", age=40).put()

        post_put_results = list(QueryTestModel.query().filter(QueryTestModel.age >= 20).fetch())
        assert len(post_put_results) == 2

    final_results = list(QueryTestModel.query().filter(QueryTestModel.age >= 20).fetch())
    assert len(final_results) == 3
