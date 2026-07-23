from unittest.mock import patch


def test_google_auth_creates_new_user(client):
    fake_info = {"email": "newuser@gmail.com", "sub": "google-sub-123"}
    with patch("app.api.routes.auth.id_token.verify_oauth2_token", return_value=fake_info):
        response = client.post("/api/v1/auth/google", json={"id_token": "fake-token"})
    assert response.status_code == 200
    body = response.json()
    assert "access_token" in body


def test_google_auth_links_existing_user_by_email(client):
    client.post(
        "/api/v1/auth/register",
        json={"organization_name": "Acme Inc", "email": "existing@acme.com", "password": "password123"},
    )
    fake_info = {"email": "existing@acme.com", "sub": "google-sub-456"}
    with patch("app.api.routes.auth.id_token.verify_oauth2_token", return_value=fake_info):
        response = client.post("/api/v1/auth/google", json={"id_token": "fake-token"})
    assert response.status_code == 200


def test_google_auth_rejects_invalid_token(client):
    with patch("app.api.routes.auth.id_token.verify_oauth2_token", side_effect=ValueError("bad token")):
        response = client.post("/api/v1/auth/google", json={"id_token": "bad"})
    assert response.status_code == 401
    assert response.json()["code"] == "invalid_token"
