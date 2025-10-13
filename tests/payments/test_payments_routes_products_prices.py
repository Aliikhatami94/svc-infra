import pytest

from tests.payments.conftest import create_mock_object

IDEMP = {"Idempotency-Key": "product-test-1"}


@pytest.mark.asyncio
async def test_create_product(client, fake_adapter, mocker):
    """Test product creation"""
    mock_product = create_mock_object(
        mocker,
        id="prod_1",
        provider="stripe",
        provider_product_id="prod_123",
        name="Test Product",
        active=True,
    )
    fake_adapter.create_product.return_value = mock_product

    res = await client.post(
        "/payments/products", json={"name": "Test Product", "active": True}, headers=IDEMP
    )

    assert res.status_code == 201
    body = res.json()
    assert body["provider_product_id"] == "prod_123"
    assert body["name"] == "Test Product"
    assert body["active"] is True

    fake_adapter.create_product.assert_awaited_once()


@pytest.mark.asyncio
async def test_get_product(client, fake_adapter, mocker):
    """Test getting a specific product"""
    mock_product = create_mock_object(
        mocker,
        id="prod_1",
        provider="stripe",
        provider_product_id="prod_123",
        name="Test Product",
        active=True,
    )
    fake_adapter.get_product.return_value = mock_product

    res = await client.get("/payments/products/prod_123")
    assert res.status_code == 200
    body = res.json()
    assert body["provider_product_id"] == "prod_123"
    assert body["name"] == "Test Product"

    fake_adapter.get_product.assert_awaited_once_with("prod_123")


@pytest.mark.asyncio
async def test_list_products(client, fake_adapter, mocker):
    """Test product listing with pagination"""
    products = [
        create_mock_object(
            mocker,
            id="prod_1",
            provider="stripe",
            provider_product_id="prod_123",
            name="Product 1",
            active=True,
        ),
        create_mock_object(
            mocker,
            id="prod_2",
            provider="stripe",
            provider_product_id="prod_456",
            name="Product 2",
            active=False,
        ),
    ]
    fake_adapter.list_products.return_value = (products, "cursor_next")

    res = await client.get("/payments/products")
    assert res.status_code == 200
    body = res.json()
    assert len(body["items"]) == 2
    assert body["next_cursor"] == "cursor_next"
    assert body["items"][0]["provider_product_id"] == "prod_123"

    fake_adapter.list_products.assert_awaited_once()


@pytest.mark.asyncio
async def test_list_products_with_active_filter(client, fake_adapter, mocker):
    """Test product listing with active filter"""
    fake_adapter.list_products.return_value = ([], None)

    res = await client.get("/payments/products?active=true")
    assert res.status_code == 200

    fake_adapter.list_products.assert_awaited_once_with(active=True, limit=50, cursor=None)


@pytest.mark.asyncio
async def test_update_product(client, fake_adapter, mocker):
    """Test product update"""
    mock_product = create_mock_object(
        mocker,
        id="prod_1",
        provider="stripe",
        provider_product_id="prod_123",
        name="Updated Product",
        active=False,
    )
    fake_adapter.update_product.return_value = mock_product

    res = await client.post(
        "/payments/products/prod_123",
        json={"name": "Updated Product", "active": False},
        headers=IDEMP,
    )

    assert res.status_code == 200
    body = res.json()
    assert body["name"] == "Updated Product"
    assert body["active"] is False

    fake_adapter.update_product.assert_awaited_once()


@pytest.mark.asyncio
async def test_create_price(client, fake_adapter, mocker):
    """Test price creation"""
    mock_price = create_mock_object(
        mocker,
        id="price_1",
        provider="stripe",
        provider_price_id="price_123",
        provider_product_id="prod_123",
        currency="USD",
        unit_amount=1000,
        interval="month",
        trial_days=7,
        active=True,
    )
    fake_adapter.create_price.return_value = mock_price

    res = await client.post(
        "/payments/prices",
        json={
            "provider_product_id": "prod_123",
            "currency": "USD",
            "unit_amount": 1000,
            "interval": "month",
            "trial_days": 7,
            "active": True,
        },
        headers=IDEMP,
    )

    assert res.status_code == 201
    body = res.json()
    assert body["provider_price_id"] == "price_123"
    assert body["currency"] == "USD"
    assert body["unit_amount"] == 1000
    assert body["interval"] == "month"
    assert body["trial_days"] == 7

    fake_adapter.create_price.assert_awaited_once()


@pytest.mark.asyncio
async def test_get_price(client, fake_adapter, mocker):
    """Test getting a specific price"""
    fake_adapter.get_price.return_value = mocker.Mock(
        id="price_1",
        provider="stripe",
        provider_price_id="price_123",
        provider_product_id="prod_123",
        currency="USD",
        unit_amount=1000,
        interval="month",
        trial_days=7,
        active=True,
    )

    res = await client.get("/payments/prices/price_123")
    assert res.status_code == 200
    body = res.json()
    assert body["provider_price_id"] == "price_123"
    assert body["currency"] == "USD"
    assert body["unit_amount"] == 1000

    fake_adapter.get_price.assert_awaited_once_with("price_123")


@pytest.mark.asyncio
async def test_list_prices(client, fake_adapter, mocker):
    """Test price listing with pagination"""
    fake_adapter.list_prices.return_value = (
        [
            mocker.Mock(
                id="price_1",
                provider="stripe",
                provider_price_id="price_123",
                provider_product_id="prod_123",
                currency="USD",
                unit_amount=1000,
                interval="month",
                trial_days=7,
                active=True,
            ),
            mocker.Mock(
                id="price_2",
                provider="stripe",
                provider_price_id="price_456",
                provider_product_id="prod_123",
                currency="USD",
                unit_amount=2000,
                interval="year",
                trial_days=None,
                active=True,
            ),
        ],
        "cursor_next",
    )

    res = await client.get("/payments/prices")
    assert res.status_code == 200
    body = res.json()
    assert len(body["items"]) == 2
    assert body["next_cursor"] == "cursor_next"
    assert body["items"][0]["provider_price_id"] == "price_123"

    fake_adapter.list_prices.assert_awaited_once()


@pytest.mark.asyncio
async def test_list_prices_with_filters(client, fake_adapter, mocker):
    """Test price listing with filters"""
    fake_adapter.list_prices.return_value = ([], None)

    res = await client.get("/payments/prices?provider_product_id=prod_123&active=true")
    assert res.status_code == 200

    fake_adapter.list_prices.assert_awaited_once_with(
        provider_product_id="prod_123", active=True, limit=50, cursor=None
    )


@pytest.mark.asyncio
async def test_update_price(client, fake_adapter, mocker):
    """Test price update"""
    mock_price = create_mock_object(
        mocker,
        id="price_1",
        provider="stripe",
        provider_price_id="price_123",
        provider_product_id="prod_123",
        currency="USD",
        unit_amount=1000,
        interval="month",
        trial_days=7,
        active=False,
    )
    fake_adapter.update_price.return_value = mock_price

    res = await client.post("/payments/prices/price_123", json={"active": False}, headers=IDEMP)

    assert res.status_code == 200
    body = res.json()
    assert body["active"] is False

    fake_adapter.update_price.assert_awaited_once()
