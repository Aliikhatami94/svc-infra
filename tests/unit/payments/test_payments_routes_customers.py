import pytest

from tests.unit.payments.conftest import create_mock_object

IDEMP = {"Idempotency-Key": "customer-test-1"}


@pytest.mark.asyncio
async def test_create_customer(client, fake_adapter, mocker):
    """Test customer creation/upsert"""
    mock_customer = create_mock_object(
        mocker,
        id="cus_1",
        provider="stripe",
        provider_customer_id="cus_123",
        email="test@example.com",
        name="Test Customer",
    )
    fake_adapter.ensure_customer.return_value = mock_customer

    res = await client.post(
        "/payments/customers",
        json={"user_id": "user_123", "email": "test@example.com", "name": "Test Customer"},
        headers=IDEMP,
    )

    assert res.status_code == 200
    body = res.json()
    assert body["provider_customer_id"] == "cus_123"
    assert body["email"] == "test@example.com"
    assert body["name"] == "Test Customer"

    fake_adapter.ensure_customer.assert_awaited_once()


@pytest.mark.asyncio
async def test_list_customers(client, fake_adapter, mocker):
    """Test customer listing with pagination"""
    customers = [
        create_mock_object(
            mocker,
            id="cus_1",
            provider="stripe",
            provider_customer_id="cus_123",
            email="test1@example.com",
            name="Customer 1",
        ),
        create_mock_object(
            mocker,
            id="cus_2",
            provider="stripe",
            provider_customer_id="cus_456",
            email="test2@example.com",
            name="Customer 2",
        ),
    ]
    fake_adapter.list_customers.return_value = (customers, "cursor_next")

    res = await client.get("/payments/customers")
    assert res.status_code == 200
    body = res.json()
    assert len(body["items"]) == 2
    assert body["next_cursor"] == "cursor_next"
    assert body["items"][0]["provider_customer_id"] == "cus_123"

    fake_adapter.list_customers.assert_awaited_once()


@pytest.mark.asyncio
async def test_list_customers_with_filters(client, fake_adapter, mocker):
    """Test customer listing with filters"""
    fake_adapter.list_customers.return_value = ([], None)

    res = await client.get("/payments/customers?provider=stripe&user_id=user_123")
    assert res.status_code == 200

    # Verify the adapter was called with correct filters
    from svc_infra.apf_payments.schemas import CustomersListFilter

    fake_adapter.list_customers.assert_awaited_once()
    call_args = fake_adapter.list_customers.await_args[0][0]
    assert isinstance(call_args, CustomersListFilter)
    assert call_args.provider == "stripe"
    assert call_args.user_id == "user_123"
    assert call_args.limit == 50
    assert call_args.cursor is None


@pytest.mark.asyncio
async def test_get_customer(client, fake_adapter, mocker):
    """Test getting a specific customer"""
    mock_customer = create_mock_object(
        mocker,
        id="cus_1",
        provider="stripe",
        provider_customer_id="cus_123",
        email="test@example.com",
        name="Test Customer",
    )
    fake_adapter.get_customer.return_value = mock_customer

    res = await client.get("/payments/customers/cus_123")
    assert res.status_code == 200
    body = res.json()
    assert body["provider_customer_id"] == "cus_123"
    assert body["email"] == "test@example.com"

    fake_adapter.get_customer.assert_awaited_once_with("cus_123")


@pytest.mark.asyncio
async def test_customer_not_found(client, fake_adapter):
    """Test handling when customer is not found"""
    fake_adapter.get_customer.return_value = None

    res = await client.get("/payments/customers/nonexistent")
    assert res.status_code == 500  # RuntimeError is raised in service
