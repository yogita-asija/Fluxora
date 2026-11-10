import uuid
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import select

from app.models import Inventory, Order, OutboxEvent
from tests.conftest import auth_headers


def post_order(client, headers, items, key=None):
    return client.post(
        "/api/v1/orders",
        json={"items": [{"product_id": str(p.id), "quantity": q} for p, q in items]},
        headers={**headers, "Idempotency-Key": key or f"key-{uuid.uuid4()}"},
    )


# ---------------------------------------------------------------------- create
def test_create_order_computes_total_on_the_server_and_writes_outbox_event(
    client, db, customer, headers, make_product
):
    keyboard = make_product(price="33.33")
    mouse = make_product(price="10.00")

    response = post_order(client, headers, [(keyboard, 3), (mouse, 1)], key="order-key-0001")

    assert response.status_code == 201
    body = response.json()
    assert body["status"] == "pending"
    assert body["user_id"] == str(customer.id)
    assert body["total_amount"] == "109.99"  # 33.33 * 3 + 10.00, exact decimal arithmetic
    assert {i["product_id"]: i["quantity"] for i in body["items"]} == {
        str(keyboard.id): 3,
        str(mouse.id): 1,
    }
    assert body["items"][0]["line_total"] in ("99.99", "10.00")
    assert body["items"][0]["product_name"] and body["items"][0]["product_sku"]

    events = db.scalars(select(OutboxEvent)).all()
    assert len(events) == 1
    event = events[0]
    assert event.event_type == "order.created"
    assert event.aggregate_type == "order"
    assert str(event.aggregate_id) == body["id"]
    assert event.status == "pending"
    assert event.payload["total_amount"] == "109.99"
    assert sorted(i["quantity"] for i in event.payload["items"]) == [1, 3]


def test_order_price_snapshot_survives_later_price_changes(client, db, headers, make_product):
    product = make_product(price="20.00")
    order = post_order(client, headers, [(product, 2)]).json()

    product.price = 99
    db.commit()

    fetched = client.get(f"/api/v1/orders/{order['id']}", headers=headers).json()
    assert fetched["items"][0]["unit_price"] == "20.00"
    assert fetched["total_amount"] == "40.00"


def test_creating_an_order_does_not_touch_stock_yet(client, db, headers, make_product):
    product = make_product(stock=5)
    assert post_order(client, headers, [(product, 4)]).status_code == 201
    inventory = db.scalar(select(Inventory).where(Inventory.product_id == product.id))
    assert (inventory.quantity_on_hand, inventory.quantity_reserved) == (5, 0)  # Phase 4 reserves


def test_client_cannot_set_price_total_status_or_user(client, headers, make_product):
    product = make_product()
    for extra in ({"price": "0.01"}, {"unit_price": "0.01"}, {"status": "paid"}, {"user_id": "x"}):
        response = client.post(
            "/api/v1/orders",
            json={"items": [{"product_id": str(product.id), "quantity": 1, **extra}]},
            headers={**headers, "Idempotency-Key": "order-key-0001"},
        )
        assert response.status_code == 422, extra
    for extra in ({"total_amount": "0.01"}, {"status": "paid"}, {"user_id": "x"}):
        response = client.post(
            "/api/v1/orders",
            json={"items": [{"product_id": str(product.id), "quantity": 1}], **extra},
            headers={**headers, "Idempotency-Key": "order-key-0002"},
        )
        assert response.status_code == 422, extra


def test_create_requires_authentication(client, make_product):
    product = make_product()
    response = client.post(
        "/api/v1/orders",
        json={"items": [{"product_id": str(product.id), "quantity": 1}]},
        headers={"Idempotency-Key": "order-key-0001"},
    )
    assert response.status_code == 401


@pytest.mark.parametrize(
    "items_factory",
    [
        lambda p: [],
        lambda p: [{"product_id": str(p.id), "quantity": 0}],
        lambda p: [{"product_id": str(p.id), "quantity": -1}],
        lambda p: [{"product_id": str(p.id), "quantity": 101}],
        lambda p: [{"product_id": str(p.id), "quantity": 1.5}],
        lambda p: [{"product_id": "not-a-uuid", "quantity": 1}],
        lambda p: [{"product_id": str(p.id), "quantity": 1}] * 2,  # duplicate product
        lambda p: [{"product_id": str(uuid.uuid4()), "quantity": 1}] * 51,  # too many lines
    ],
)
def test_invalid_item_lists_are_rejected(client, headers, make_product, items_factory):
    product = make_product()
    response = client.post(
        "/api/v1/orders",
        json={"items": items_factory(product)},
        headers={**headers, "Idempotency-Key": "order-key-0001"},
    )
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "validation_error"


@pytest.mark.parametrize("key", [None, "short", "has space in it", "bad/slash/key", "k" * 129])
def test_idempotency_key_is_required_and_well_formed(client, headers, make_product, key):
    product = make_product()
    request_headers = dict(headers)
    if key is not None:
        request_headers["Idempotency-Key"] = key
    response = client.post(
        "/api/v1/orders",
        json={"items": [{"product_id": str(product.id), "quantity": 1}]},
        headers=request_headers,
    )
    assert response.status_code == 422


def test_unknown_and_inactive_products_are_rejected_with_details(
    client, db, headers, make_product
):
    inactive = make_product(is_active=False)
    ghost = uuid.uuid4()
    response = client.post(
        "/api/v1/orders",
        json={
            "items": [
                {"product_id": str(inactive.id), "quantity": 1},
                {"product_id": str(ghost), "quantity": 1},
            ]
        },
        headers={**headers, "Idempotency-Key": "order-key-0001"},
    )
    assert response.status_code == 422
    reasons = {d["product_id"]: d["reason"] for d in response.json()["error"]["details"]}
    assert reasons == {str(inactive.id): "inactive", str(ghost): "not_found"}
    assert db.scalars(select(Order)).all() == []
    assert db.scalars(select(OutboxEvent)).all() == []


# ---------------------------------------------------------------- idempotency
def test_same_key_and_request_returns_the_original_order_once(
    client, db, headers, make_product
):
    product = make_product()
    first = post_order(client, headers, [(product, 2)], key="retry-me-0001")
    second = post_order(client, headers, [(product, 2)], key="retry-me-0001")

    assert first.status_code == 201
    assert second.status_code == 200
    assert first.json() == second.json()
    assert len(db.scalars(select(Order)).all()) == 1
    assert len(db.scalars(select(OutboxEvent)).all()) == 1


def test_same_key_with_a_different_request_is_a_conflict(client, db, headers, make_product):
    product, other = make_product(), make_product()
    assert post_order(client, headers, [(product, 1)], key="retry-me-0001").status_code == 201

    for items in ([(product, 2)], [(other, 1)], [(product, 1), (other, 1)]):
        response = post_order(client, headers, items, key="retry-me-0001")
        assert response.status_code == 409
        assert response.json()["error"]["code"] == "idempotency_key_reused"
    assert len(db.scalars(select(Order)).all()) == 1


def test_item_order_does_not_change_the_request_fingerprint(client, headers, make_product):
    a, b = make_product(), make_product()
    assert post_order(client, headers, [(a, 1), (b, 2)], key="retry-me-0001").status_code == 201
    assert post_order(client, headers, [(b, 2), (a, 1)], key="retry-me-0001").status_code == 200


def test_idempotency_keys_are_scoped_per_user(client, db, headers, make_user, make_product):
    product = make_product()
    other_headers = auth_headers(make_user("second@example.com"))

    mine = post_order(client, headers, [(product, 1)], key="shared-key-0001")
    theirs = post_order(client, other_headers, [(product, 1)], key="shared-key-0001")

    assert mine.status_code == theirs.status_code == 201
    assert mine.json()["id"] != theirs.json()["id"]  # no cross-user collision or leak


# ------------------------------------------------------------------- list/get
def test_customers_only_see_their_own_orders(client, headers, make_user, make_product):
    product = make_product()
    other_headers = auth_headers(make_user("second@example.com"))
    mine = post_order(client, headers, [(product, 1)]).json()
    post_order(client, other_headers, [(product, 1)])

    page = client.get("/api/v1/orders", headers=headers).json()
    assert page["total"] == 1
    assert [o["id"] for o in page["items"]] == [mine["id"]]


def test_admin_sees_all_orders(client, headers, admin, make_user, make_product):
    product = make_product()
    other_headers = auth_headers(make_user("second@example.com"))
    post_order(client, headers, [(product, 1)])
    post_order(client, other_headers, [(product, 1)])

    page = client.get("/api/v1/orders", headers=auth_headers(admin)).json()
    assert page["total"] == 2


def test_list_pagination_filter_and_order(client, db, headers, make_product):
    product = make_product()
    ids = [post_order(client, headers, [(product, 1)]).json()["id"] for _ in range(3)]
    # Distinct creation times (SQLite's default clock only has 1-second resolution).
    for i, order_id in enumerate(ids):
        db.get(Order, uuid.UUID(order_id)).created_at = datetime(2026, 1, 1, tzinfo=UTC) + timedelta(hours=i)
    db.commit()
    client.post(f"/api/v1/orders/{ids[0]}/cancel", headers=headers)

    page = client.get("/api/v1/orders", params={"limit": 2}, headers=headers).json()
    assert (page["total"], page["limit"], page["offset"], len(page["items"])) == (3, 2, 0, 2)
    assert page["items"][0]["id"] == ids[2]  # newest first

    rest = client.get("/api/v1/orders", params={"limit": 2, "offset": 2}, headers=headers).json()
    assert len(rest["items"]) == 1

    cancelled = client.get("/api/v1/orders", params={"status": "cancelled"}, headers=headers)
    assert [o["id"] for o in cancelled.json()["items"]] == [ids[0]]


@pytest.mark.parametrize(
    "params", [{"status": "nonsense"}, {"limit": 0}, {"limit": 101}, {"offset": -1}]
)
def test_list_rejects_bad_query_params(client, headers, params):
    assert client.get("/api/v1/orders", params=params, headers=headers).status_code == 422


def test_list_requires_authentication(client):
    assert client.get("/api/v1/orders").status_code == 401


def test_other_users_order_looks_like_it_does_not_exist(client, headers, make_user, make_product):
    product = make_product()
    other_headers = auth_headers(make_user("second@example.com"))
    order = post_order(client, headers, [(product, 1)]).json()

    stranger = client.get(f"/api/v1/orders/{order['id']}", headers=other_headers)
    missing = client.get(f"/api/v1/orders/{uuid.uuid4()}", headers=other_headers)

    assert stranger.status_code == missing.status_code == 404
    assert stranger.json() == missing.json()  # indistinguishable: ids can't be probed


def test_admin_can_open_any_order(client, headers, admin, make_product):
    order = post_order(client, headers, [(make_product(), 1)]).json()
    assert client.get(f"/api/v1/orders/{order['id']}", headers=auth_headers(admin)).status_code == 200


def test_get_order_validates_id(client, headers):
    assert client.get("/api/v1/orders/not-a-uuid", headers=headers).status_code == 422


# ---------------------------------------------------------------------- cancel
def test_cancel_pending_order_writes_event_in_same_transaction(
    client, db, headers, customer, make_product
):
    order = post_order(client, headers, [(make_product(), 1)]).json()

    response = client.post(f"/api/v1/orders/{order['id']}/cancel", headers=headers)

    assert response.status_code == 200
    assert response.json()["status"] == "cancelled"
    types = sorted(e.event_type for e in db.scalars(select(OutboxEvent)))
    assert types == ["order.cancelled", "order.created"]
    cancelled = next(e for e in db.scalars(select(OutboxEvent)) if e.event_type == "order.cancelled")
    assert cancelled.payload["cancelled_by"] == str(customer.id)


def test_cancelling_twice_is_a_conflict_and_writes_one_event(client, db, headers, make_product):
    order = post_order(client, headers, [(make_product(), 1)]).json()
    assert client.post(f"/api/v1/orders/{order['id']}/cancel", headers=headers).status_code == 200

    again = client.post(f"/api/v1/orders/{order['id']}/cancel", headers=headers)
    assert again.status_code == 409
    assert again.json()["error"]["code"] == "conflict"
    cancelled = [e for e in db.scalars(select(OutboxEvent)) if e.event_type == "order.cancelled"]
    assert len(cancelled) == 1


@pytest.mark.parametrize("status", ["reserved", "paid", "fulfilled", "failed"])
def test_orders_past_pending_cannot_be_cancelled(client, db, headers, make_product, status):
    order = post_order(client, headers, [(make_product(), 1)]).json()
    row = db.get(Order, uuid.UUID(order["id"]))
    row.status = status
    db.commit()

    response = client.post(f"/api/v1/orders/{order['id']}/cancel", headers=headers)
    assert response.status_code == 409
    db.refresh(row)
    assert row.status == status


def test_cannot_cancel_someone_elses_order(client, db, headers, make_user, make_product):
    order = post_order(client, headers, [(make_product(), 1)]).json()
    other_headers = auth_headers(make_user("second@example.com"))

    response = client.post(f"/api/v1/orders/{order['id']}/cancel", headers=other_headers)

    assert response.status_code == 404
    assert db.get(Order, uuid.UUID(order["id"])).status == "pending"


def test_admin_can_cancel_any_pending_order(client, db, headers, admin, make_product):
    order = post_order(client, headers, [(make_product(), 1)]).json()
    response = client.post(f"/api/v1/orders/{order['id']}/cancel", headers=auth_headers(admin))
    assert response.status_code == 200


def test_cancel_requires_authentication(client, headers, make_product):
    order = post_order(client, headers, [(make_product(), 1)]).json()
    assert client.post(f"/api/v1/orders/{order['id']}/cancel").status_code == 401
