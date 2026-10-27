import uuid

from app.core.database import get_db
from app.main import app


def assert_error_shape(body: dict, code: str) -> None:
    assert set(body) == {"error"}
    assert set(body["error"]) == {"code", "message", "details"}
    assert body["error"]["code"] == code


def test_unknown_route_returns_structured_404(client):
    response = client.get("/api/v1/does-not-exist")
    assert response.status_code == 404
    assert_error_shape(response.json(), "not_found")


def test_missing_resource_returns_structured_404(client):
    response = client.get(f"/api/v1/products/{uuid.uuid4()}")
    assert response.status_code == 404
    assert_error_shape(response.json(), "not_found")


def test_validation_error_returns_structured_422(client):
    response = client.get("/api/v1/products/not-a-uuid")
    assert response.status_code == 422
    body = response.json()
    assert_error_shape(body, "validation_error")
    assert body["error"]["details"][0]["loc"] == ["path", "product_id"]


def test_unexpected_error_returns_structured_500_without_leaking_details(client):
    def explode():
        raise RuntimeError("secret internal detail")

    app.dependency_overrides[get_db] = explode

    response = client.get("/api/v1/products")
    assert response.status_code == 500
    assert_error_shape(response.json(), "internal_error")
    assert "secret" not in response.text
