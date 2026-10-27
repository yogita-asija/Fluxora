from decimal import Decimal

from app.models import Product


def make_product(db, sku="TEST-1", name="Test Product", price="12.50") -> Product:
    product = Product(sku=sku, name=name, price=Decimal(price))
    db.add(product)
    db.commit()
    return product


def test_list_products_empty(client):
    response = client.get("/api/v1/products")
    assert response.status_code == 200
    assert response.json() == []


def test_list_products_returns_rows_ordered_by_name(client, db):
    make_product(db, sku="B", name="Banana")
    make_product(db, sku="A", name="Apple")

    response = client.get("/api/v1/products")
    assert response.status_code == 200
    assert [p["name"] for p in response.json()] == ["Apple", "Banana"]


def test_list_products_pagination(client, db):
    for i in range(3):
        make_product(db, sku=f"SKU-{i}", name=f"Product {i}")

    response = client.get("/api/v1/products", params={"limit": 2, "offset": 2})
    assert [p["name"] for p in response.json()] == ["Product 2"]


def test_list_products_rejects_invalid_limit(client):
    assert client.get("/api/v1/products", params={"limit": 0}).status_code == 422


def test_get_product(client, db):
    product = make_product(db)

    response = client.get(f"/api/v1/products/{product.id}")
    assert response.status_code == 200
    body = response.json()
    assert body["sku"] == "TEST-1"
    assert float(body["price"]) == 12.5
    assert body["is_active"] is True


def test_cors_allows_configured_origin(client):
    response = client.options(
        "/api/v1/products",
        headers={
            "Origin": "http://localhost:5173",
            "Access-Control-Request-Method": "GET",
        },
    )
    assert response.headers["access-control-allow-origin"] == "http://localhost:5173"
