from sqlalchemy.exc import OperationalError

from app.core.database import get_db
from app.main import app


def test_live(client):
    response = client.get("/health/live")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_ready_when_database_is_up(client):
    response = client.get("/health/ready")
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "checks": {"database": "ok"}}


def test_ready_returns_503_when_database_is_down(client):
    class BrokenSession:
        def execute(self, *args, **kwargs):
            raise OperationalError("SELECT 1", {}, Exception("database down"))

    app.dependency_overrides[get_db] = lambda: BrokenSession()

    response = client.get("/health/ready")
    assert response.status_code == 503
    assert response.json() == {"status": "unavailable", "checks": {"database": "unavailable"}}

    # Liveness must not depend on the database.
    assert client.get("/health/live").status_code == 200


def test_metrics_endpoint_records_requests_by_route_template(client):
    client.get("/health/live")
    client.get("/api/v1/products/not-a-uuid")  # 422, still counted
    client.get("/no/such/path")  # unmatched paths share one label

    body = client.get("/metrics").text
    assert 'http_requests_total{handler="/health/live",method="GET",status="200"}' in body
    assert 'handler="/api/v1/products/{product_id}"' in body
    assert 'handler="unmatched"' in body
    assert "/no/such/path" not in body
