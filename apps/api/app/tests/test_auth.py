def test_register_creates_org_and_user(client):
    response = client.post(
        "/api/v1/auth/register",
        json={"organization_name": "Acme Inc", "email": "founder@acme.com", "password": "password123"},
    )
    assert response.status_code == 201
    body = response.json()
    assert "access_token" in body
    assert "refresh_token" in body


def test_register_rejects_duplicate_email(client):
    payload = {"organization_name": "Acme Inc", "email": "dup@acme.com", "password": "password123"}
    client.post("/api/v1/auth/register", json=payload)
    response = client.post("/api/v1/auth/register", json=payload)
    assert response.status_code == 409
    assert response.json()["code"] == "conflict"


def test_login_succeeds_with_correct_password(client):
    client.post(
        "/api/v1/auth/register",
        json={"organization_name": "Acme Inc", "email": "login@acme.com", "password": "password123"},
    )
    response = client.post("/api/v1/auth/login", json={"email": "login@acme.com", "password": "password123"})
    assert response.status_code == 200
    assert "access_token" in response.json()


def test_login_rejects_wrong_password(client):
    client.post(
        "/api/v1/auth/register",
        json={"organization_name": "Acme Inc", "email": "wrong@acme.com", "password": "password123"},
    )
    response = client.post("/api/v1/auth/login", json={"email": "wrong@acme.com", "password": "nope"})
    assert response.status_code == 401
    assert response.json()["code"] == "invalid_credentials"


def test_me_requires_auth(client):
    response = client.get("/api/v1/auth/me")
    assert response.status_code == 401


def test_me_returns_current_user(client):
    register = client.post(
        "/api/v1/auth/register",
        json={"organization_name": "Acme Inc", "email": "me@acme.com", "password": "password123"},
    )
    token = register.json()["access_token"]
    response = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 200
    assert response.json()["email"] == "me@acme.com"


def test_refresh_issues_new_access_token(client):
    register = client.post(
        "/api/v1/auth/register",
        json={"organization_name": "Acme Inc", "email": "refresh@acme.com", "password": "password123"},
    )
    refresh_token = register.json()["refresh_token"]
    response = client.post("/api/v1/auth/refresh", json={"refresh_token": refresh_token})
    assert response.status_code == 200
    assert "access_token" in response.json()
