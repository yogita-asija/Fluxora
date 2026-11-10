from sqlalchemy import select

from app.models import User
from tests.conftest import PASSWORD, auth_headers

REGISTER = {"email": "New.User@Example.com", "full_name": "New User", "password": PASSWORD}


def login(client, email="user@example.com", password=PASSWORD):
    return client.post("/api/v1/auth/login", json={"email": email, "password": password})


# ---------------------------------------------------------------- registration
def test_register_creates_customer_without_leaking_hash(client, db):
    response = client.post("/api/v1/auth/register", json=REGISTER)

    assert response.status_code == 201
    body = response.json()
    assert body["email"] == "new.user@example.com"  # normalised
    assert body["role"] == "customer"
    assert "password" not in body and "password_hash" not in body

    stored = db.scalar(select(User).where(User.email == "new.user@example.com"))
    assert stored.password_hash.startswith("$argon2id$")
    assert PASSWORD not in stored.password_hash


def test_register_duplicate_email_is_rejected_case_insensitively(client):
    assert client.post("/api/v1/auth/register", json=REGISTER).status_code == 201
    again = client.post("/api/v1/auth/register", json={**REGISTER, "email": "NEW.user@example.com"})
    assert again.status_code == 409


def test_register_cannot_choose_role_or_other_fields(client):
    for extra in ({"role": "admin"}, {"is_active": False}, {"id": "x"}):
        response = client.post("/api/v1/auth/register", json={**REGISTER, **extra})
        assert response.status_code == 422, extra


def test_register_validates_input(client):
    bad = [
        {**REGISTER, "password": "short"},
        {**REGISTER, "password": "x" * 129},
        {**REGISTER, "email": "not-an-email"},
        {**REGISTER, "email": "a@b"},
        {**REGISTER, "full_name": "   "},
        {**REGISTER, "full_name": "x" * 256},
    ]
    for payload in bad:
        assert client.post("/api/v1/auth/register", json=payload).status_code == 422, payload


def test_validation_errors_do_not_echo_the_password(client):
    response = client.post("/api/v1/auth/register", json={**REGISTER, "password": "short-pw"})
    assert response.status_code == 422
    assert "short-pw" not in response.text


# ----------------------------------------------------------------------- login
def test_login_returns_working_token(client, customer):
    response = login(client, customer.email)
    assert response.status_code == 200
    body = response.json()
    assert body["token_type"] == "bearer"
    assert body["expires_in"] == 30 * 60

    me = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {body['access_token']}"})
    assert me.status_code == 200
    assert me.json()["email"] == customer.email


def test_login_email_is_case_insensitive(client, customer):
    assert login(client, customer.email.upper()).status_code == 200


def test_login_failures_are_indistinguishable(client, customer):
    wrong_password = login(client, customer.email, "wrong-password-123")
    unknown_email = login(client, "nobody@example.com")

    assert wrong_password.status_code == unknown_email.status_code == 401
    assert wrong_password.json() == unknown_email.json()
    assert wrong_password.headers["www-authenticate"] == "Bearer"


def test_inactive_account_cannot_log_in_with_correct_password(client, make_user):
    user = make_user("gone@example.com", is_active=False)
    response = login(client, user.email)
    assert response.status_code == 401
    assert response.json() == login(client, "nobody@example.com").json()


def test_account_with_unusable_password_cannot_log_in(client, make_user, db):
    user = make_user("legacy@example.com")
    user.password_hash = "!"
    db.commit()
    assert login(client, user.email, "!").status_code == 401
    assert login(client, user.email).status_code == 401


def test_account_locks_after_repeated_failures_and_success_resets_counter(client, customer):
    for _ in range(4):
        assert login(client, customer.email, "wrong-password-123").status_code == 401
    # A correct login before the limit resets the counter...
    assert login(client, customer.email).status_code == 200
    for _ in range(5):
        assert login(client, customer.email, "wrong-password-123").status_code == 401

    # ...but after 5 consecutive failures even the right password is refused.
    locked = login(client, customer.email)
    assert locked.status_code == 429
    assert int(locked.headers["retry-after"]) > 0
    assert locked.json()["error"]["code"] == "too_many_requests"


def test_lockout_is_per_account(client, customer, make_user):
    other = make_user("other@example.com")
    for _ in range(5):
        login(client, customer.email, "wrong-password-123")
    assert login(client, customer.email).status_code == 429
    assert login(client, other.email).status_code == 200


def test_lockout_applies_to_unknown_emails_too(client):
    for _ in range(5):
        login(client, "ghost@example.com", "wrong-password-123")
    assert login(client, "ghost@example.com").status_code == 429


def test_login_rejects_unexpected_fields_and_oversized_passwords(client, customer):
    assert client.post(
        "/api/v1/auth/login",
        json={"email": customer.email, "password": PASSWORD, "remember": True},
    ).status_code == 422
    assert login(client, customer.email, "x" * 129).status_code == 422


# ---------------------------------------------------------------------- tokens
def test_me_requires_a_token(client):
    response = client.get("/api/v1/auth/me")
    assert response.status_code == 401
    assert response.headers["www-authenticate"] == "Bearer"
    assert response.json()["error"]["code"] == "unauthorized"


def test_me_rejects_garbage_and_wrong_scheme(client, headers):
    token = headers["Authorization"].split()[1]
    for value in ("Bearer garbage", "Bearer ", "Basic abc", token, "Bearer a.b.c"):
        assert client.get("/api/v1/auth/me", headers={"Authorization": value}).status_code == 401


def test_token_for_deleted_or_disabled_user_stops_working(client, db, make_user):
    user = make_user("temp@example.com")
    headers = auth_headers(user)
    assert client.get("/api/v1/auth/me", headers=headers).status_code == 200

    user.is_active = False
    db.commit()
    assert client.get("/api/v1/auth/me", headers=headers).status_code == 401

    db.delete(user)
    db.commit()
    assert client.get("/api/v1/auth/me", headers=headers).status_code == 401
