import pytest

IDEMP = {"Idempotency-Key": "invoice-test-1"}


@pytest.mark.asyncio
async def test_create_invoice(client, fake_adapter, mocker):
    """Test invoice creation"""
    fake_adapter.create_invoice.return_value = mocker.Mock(
        id="inv_1",
        provider="stripe",
        provider_invoice_id="inv_123",
        provider_customer_id="cus_123",
        status="draft",
        amount_due=1000,
        currency="USD",
        hosted_invoice_url="https://invoice.stripe.com/inv_123",
        pdf_url="https://invoice.stripe.com/inv_123.pdf",
    )

    res = await client.post(
        "/payments/invoices",
        json={"customer_provider_id": "cus_123", "auto_advance": True},
        headers=IDEMP,
    )

    assert res.status_code == 201
    body = res.json()
    assert body["provider_invoice_id"] == "inv_123"
    assert body["provider_customer_id"] == "cus_123"
    assert body["status"] == "draft"
    assert body["amount_due"] == 1000
    assert body["currency"] == "USD"
    # Location header should point to GET invoice
    assert res.headers["Location"].endswith("/payments/invoices/inv_123")

    fake_adapter.create_invoice.assert_awaited_once()


@pytest.mark.asyncio
async def test_get_invoice(client, fake_adapter, mocker):
    """Test getting a specific invoice"""
    fake_adapter.get_invoice.return_value = mocker.Mock(
        id="inv_1",
        provider="stripe",
        provider_invoice_id="inv_123",
        provider_customer_id="cus_123",
        status="open",
        amount_due=1000,
        currency="USD",
        hosted_invoice_url="https://invoice.stripe.com/inv_123",
        pdf_url="https://invoice.stripe.com/inv_123.pdf",
    )

    res = await client.get("/payments/invoices/inv_123")
    assert res.status_code == 200
    body = res.json()
    assert body["provider_invoice_id"] == "inv_123"
    assert body["status"] == "open"
    assert body["amount_due"] == 1000

    fake_adapter.get_invoice.assert_awaited_once_with("inv_123")


@pytest.mark.asyncio
async def test_list_invoices(client, fake_adapter, mocker):
    """Test invoice listing with pagination"""
    fake_adapter.list_invoices.return_value = (
        [
            mocker.Mock(
                id="inv_1",
                provider="stripe",
                provider_invoice_id="inv_123",
                provider_customer_id="cus_123",
                status="open",
                amount_due=1000,
                currency="USD",
                hosted_invoice_url="https://invoice.stripe.com/inv_123",
                pdf_url="https://invoice.stripe.com/inv_123.pdf",
            ),
            mocker.Mock(
                id="inv_2",
                provider="stripe",
                provider_invoice_id="inv_456",
                provider_customer_id="cus_123",
                status="paid",
                amount_due=0,
                currency="USD",
                hosted_invoice_url="https://invoice.stripe.com/inv_456",
                pdf_url="https://invoice.stripe.com/inv_456.pdf",
            ),
        ],
        "cursor_next",
    )

    res = await client.get("/payments/invoices")
    assert res.status_code == 200
    body = res.json()
    assert len(body["items"]) == 2
    assert body["next_cursor"] == "cursor_next"
    assert body["items"][0]["provider_invoice_id"] == "inv_123"

    fake_adapter.list_invoices.assert_awaited_once()


@pytest.mark.asyncio
async def test_list_invoices_with_filters(client, fake_adapter, mocker):
    """Test invoice listing with filters"""
    fake_adapter.list_invoices.return_value = ([], None)

    res = await client.get("/payments/invoices?customer_provider_id=cus_123&status=open")
    assert res.status_code == 200

    # Verify the adapter was called with correct filters
    from svc_infra.apf_payments.schemas import InvoicesListFilter

    fake_adapter.list_invoices.assert_awaited_once()
    call_args = fake_adapter.list_invoices.await_args[0][0]
    assert isinstance(call_args, InvoicesListFilter)
    assert call_args.customer_provider_id == "cus_123"
    assert call_args.status == "open"
    assert call_args.limit == 50
    assert call_args.cursor is None


@pytest.mark.asyncio
async def test_finalize_invoice(client, fake_adapter, mocker):
    """Test invoice finalization"""
    fake_adapter.finalize_invoice.return_value = mocker.Mock(
        id="inv_1",
        provider="stripe",
        provider_invoice_id="inv_123",
        provider_customer_id="cus_123",
        status="open",
        amount_due=1000,
        currency="USD",
        hosted_invoice_url="https://invoice.stripe.com/inv_123",
        pdf_url="https://invoice.stripe.com/inv_123.pdf",
    )

    res = await client.post("/payments/invoices/inv_123/finalize", headers=IDEMP)
    assert res.status_code == 200
    body = res.json()
    assert body["provider_invoice_id"] == "inv_123"
    assert body["status"] == "open"

    fake_adapter.finalize_invoice.assert_awaited_once_with("inv_123")


@pytest.mark.asyncio
async def test_void_invoice(client, fake_adapter, mocker):
    """Test invoice voiding"""
    fake_adapter.void_invoice.return_value = mocker.Mock(
        id="inv_1",
        provider="stripe",
        provider_invoice_id="inv_123",
        provider_customer_id="cus_123",
        status="void",
        amount_due=0,
        currency="USD",
        hosted_invoice_url=None,
        pdf_url=None,
    )

    res = await client.post("/payments/invoices/inv_123/void", headers=IDEMP)
    assert res.status_code == 200
    body = res.json()
    assert body["provider_invoice_id"] == "inv_123"
    assert body["status"] == "void"
    assert body["amount_due"] == 0

    fake_adapter.void_invoice.assert_awaited_once_with("inv_123")


@pytest.mark.asyncio
async def test_pay_invoice(client, fake_adapter, mocker):
    """Test invoice payment"""
    fake_adapter.pay_invoice.return_value = mocker.Mock(
        id="inv_1",
        provider="stripe",
        provider_invoice_id="inv_123",
        provider_customer_id="cus_123",
        status="paid",
        amount_due=0,
        currency="USD",
        hosted_invoice_url="https://invoice.stripe.com/inv_123",
        pdf_url="https://invoice.stripe.com/inv_123.pdf",
    )

    res = await client.post("/payments/invoices/inv_123/pay", headers=IDEMP)
    assert res.status_code == 200
    body = res.json()
    assert body["provider_invoice_id"] == "inv_123"
    assert body["status"] == "paid"
    assert body["amount_due"] == 0

    fake_adapter.pay_invoice.assert_awaited_once_with("inv_123")


@pytest.mark.asyncio
async def test_add_invoice_line_item(client, fake_adapter, mocker):
    """Test adding line item to invoice"""
    fake_adapter.add_invoice_line_item.return_value = mocker.Mock(
        id="inv_1",
        provider="stripe",
        provider_invoice_id="inv_123",
        provider_customer_id="cus_123",
        status="draft",
        amount_due=1500,
        currency="USD",
        hosted_invoice_url=None,
        pdf_url=None,
    )

    res = await client.post(
        "/payments/invoices/inv_123/lines",
        json={
            "customer_provider_id": "cus_123",
            "description": "Additional service",
            "unit_amount": 500,
            "currency": "USD",
            "quantity": 1,
            "provider_price_id": "price_123",
        },
        headers=IDEMP,
    )

    assert res.status_code == 201
    body = res.json()
    assert body["provider_invoice_id"] == "inv_123"
    assert body["amount_due"] == 1500

    fake_adapter.add_invoice_line_item.assert_awaited_once()


@pytest.mark.asyncio
async def test_list_invoice_line_items(client, fake_adapter, mocker):
    """Test listing invoice line items"""
    fake_adapter.list_invoice_line_items.return_value = (
        [
            mocker.Mock(
                id="li_1",
                description="Service 1",
                amount=1000,
                currency="USD",
                quantity=1,
                provider_price_id="price_123",
            ),
            mocker.Mock(
                id="li_2",
                description="Service 2",
                amount=500,
                currency="USD",
                quantity=1,
                provider_price_id=None,
            ),
        ],
        "cursor_next",
    )

    res = await client.get("/payments/invoices/inv_123/lines")
    assert res.status_code == 200
    body = res.json()
    assert len(body["items"]) == 2
    assert body["next_cursor"] == "cursor_next"
    assert body["items"][0]["description"] == "Service 1"
    assert body["items"][0]["amount"] == 1000

    fake_adapter.list_invoice_line_items.assert_awaited_once()


@pytest.mark.asyncio
async def test_preview_invoice(client, fake_adapter, mocker):
    """Test invoice preview"""
    fake_adapter.preview_invoice.return_value = mocker.Mock(
        id="inv_preview",
        provider="stripe",
        provider_invoice_id="inv_preview_123",
        provider_customer_id="cus_123",
        status="draft",
        amount_due=1000,
        currency="USD",
        hosted_invoice_url=None,
        pdf_url=None,
    )

    res = await client.post(
        "/payments/invoices/preview",
        params={"customer_provider_id": "cus_123", "subscription_id": "sub_123"},
        headers=IDEMP,
    )

    assert res.status_code == 200
    body = res.json()
    assert body["provider_customer_id"] == "cus_123"
    assert body["amount_due"] == 1000

    fake_adapter.preview_invoice.assert_awaited_once_with("cus_123", "sub_123")
