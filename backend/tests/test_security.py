"""Token forgery, CORS, headers, production hardening."""

import base64
import json
import time
import uuid

import jwt
import pytest
from fastapi.testclient import TestClient

from app.core.config import Settings, get_settings
from app.core.security import ALGORITHM, create_access_token, decode_access_token
from app.main import create_app


def b64(data: dict) -> str:
    return base64.urlsafe_b64encode(json.dumps(data).encode()).rstrip(b"=").decode()


def forged(claims: dict, key: str | None = None, algorithm: str = ALGORITHM) -> str:
    return jwt.encode(claims, key or get_settings().jwt_secret_key, algorithm=algorithm)


def valid_claims(user_id, **overrides) -> dict:
    now = int(time.time())
    claims = {"sub": str(user_id), "iss": "orderflow", "iat": now, "exp": now + 600}
    claims.update(overrides)
    return claims


def me(client, token):
    return client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})


def test_a_correctly_built_token_is_accepted(client, customer):
    assert me(client, forged(valid_claims(customer.id))).status_code == 200


def test_expired_token_is_rejected(client, customer):
    token = forged(valid_claims(customer.id, exp=int(time.time()) - 10))
    assert me(client, token).status_code == 401


def test_token_signed_with_another_key_is_rejected(client, customer):
    token = forged(valid_claims(customer.id), key="x" * 40)
    assert me(client, token).status_code == 401


def test_alg_none_token_is_rejected(client, customer):
    header = b64({"alg": "none", "typ": "JWT"})
    token = f"{header}.{b64(valid_claims(customer.id))}."
    assert me(client, token).status_code == 401


def test_token_with_a_different_algorithm_is_rejected(client, customer):
    token = forged(valid_claims(customer.id), key="y" * 64, algorithm="HS512")
    assert me(client, token).status_code == 401


def test_tampered_payload_is_rejected(client, customer, admin):
    good = forged(valid_claims(customer.id))
    header, _, signature = good.split(".")
    swapped = f"{header}.{b64(valid_claims(admin.id))}.{signature}"  # keep old signature
    assert me(client, swapped).status_code == 401


@pytest.mark.parametrize(
    "overrides",
    [{"iss": "someone-else"}, {"sub": "not-a-uuid"}, {"sub": str(uuid.uuid4())}],
)
def test_token_with_bad_claims_is_rejected(client, customer, overrides):
    assert me(client, forged(valid_claims(customer.id, **overrides))).status_code == 401


@pytest.mark.parametrize("missing", ["exp", "iat", "sub", "iss"])
def test_token_missing_required_claims_is_rejected(client, customer, missing):
    claims = valid_claims(customer.id)
    del claims[missing]
    assert me(client, forged(claims)).status_code == 401


def test_role_in_token_is_ignored(client, customer):
    """Privileges come from the database, so a 'role' claim can't elevate anyone."""
    token = forged(valid_claims(customer.id, role="admin"))
    assert me(client, token).json()["role"] == "customer"


def test_token_roundtrip_helpers():
    settings = get_settings()
    user_id = uuid.uuid4()
    token, lifetime = create_access_token(user_id, settings)
    assert lifetime == settings.access_token_expire_minutes * 60
    assert decode_access_token(token, settings) == user_id


# --------------------------------------------------------------------- config
@pytest.mark.parametrize("secret", ["short", "change-me-" + "a" * 40, ""])
def test_weak_or_placeholder_jwt_secret_is_refused_at_startup(secret):
    with pytest.raises(ValueError):
        Settings(database_url="sqlite://", jwt_secret_key=secret)


# ----------------------------------------------------------------- HTTP layer
def test_api_responses_have_security_headers(client, headers):
    response = client.get("/api/v1/auth/me", headers=headers)
    assert response.headers["x-content-type-options"] == "nosniff"
    assert response.headers["cache-control"] == "no-store"


def test_cors_allows_only_configured_origin_and_headers(client):
    ok = client.options(
        "/api/v1/orders",
        headers={
            "Origin": "http://localhost:5173",
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "authorization,idempotency-key,content-type",
        },
    )
    assert ok.status_code == 200
    assert ok.headers["access-control-allow-origin"] == "http://localhost:5173"
    assert "access-control-allow-credentials" not in ok.headers

    evil = client.options(
        "/api/v1/orders",
        headers={"Origin": "https://evil.example", "Access-Control-Request-Method": "POST"},
    )
    assert "access-control-allow-origin" not in evil.headers

    bad_header = client.options(
        "/api/v1/orders",
        headers={
            "Origin": "http://localhost:5173",
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "x-anything-else",
        },
    )
    assert bad_header.status_code == 400


def test_api_docs_are_disabled_in_production():
    settings = Settings(
        database_url="sqlite://", jwt_secret_key="k" * 40, environment="production"
    )
    with TestClient(create_app(settings)) as prod:
        assert prod.get("/api/docs").status_code == 404
        assert prod.get("/api/openapi.json").status_code == 404
        assert prod.get("/health/live").status_code == 200


def test_api_docs_are_available_in_development(client):
    assert client.get("/api/docs").status_code == 200
