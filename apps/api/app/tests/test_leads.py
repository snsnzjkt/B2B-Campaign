from unittest.mock import patch


def test_create_lead_without_company(client, auth_headers):
    response = client.post(
        "/api/v1/leads", json={"contact_name": "Jane Doe", "email": "jane@example.com"}, headers=auth_headers
    )
    assert response.status_code == 201
    assert response.json()["status"] == "new"


def test_create_lead_with_valid_company(client, auth_headers):
    company = client.post("/api/v1/companies", json={"name": "Acme Corp"}, headers=auth_headers)
    company_id = company.json()["id"]
    response = client.post(
        "/api/v1/leads",
        json={"contact_name": "Jane Doe", "company_id": company_id},
        headers=auth_headers,
    )
    assert response.status_code == 201
    assert response.json()["company_id"] == company_id


def test_create_lead_with_unknown_company_404s(client, auth_headers):
    response = client.post(
        "/api/v1/leads",
        json={"contact_name": "Jane Doe", "company_id": "00000000-0000-0000-0000-000000000000"},
        headers=auth_headers,
    )
    assert response.status_code == 404


def test_list_leads_empty_by_default(client, auth_headers):
    response = client.get("/api/v1/leads", headers=auth_headers)
    assert response.status_code == 200
    assert response.json() == []


def test_update_lead_status_and_score(client, auth_headers):
    create = client.post("/api/v1/leads", json={"contact_name": "Jane Doe"}, headers=auth_headers)
    lead_id = create.json()["id"]
    response = client.patch(
        f"/api/v1/leads/{lead_id}", json={"status": "qualified", "score": 80}, headers=auth_headers
    )
    assert response.status_code == 200
    assert response.json()["status"] == "qualified"
    assert response.json()["score"] == 80


def test_delete_lead(client, auth_headers):
    create = client.post("/api/v1/leads", json={"contact_name": "Jane Doe"}, headers=auth_headers)
    lead_id = create.json()["id"]
    response = client.delete(f"/api/v1/leads/{lead_id}", headers=auth_headers)
    assert response.status_code == 204
    get_response = client.get(f"/api/v1/leads/{lead_id}", headers=auth_headers)
    assert get_response.status_code == 404


def test_leads_are_scoped_to_organization(client, auth_headers):
    client.post("/api/v1/leads", json={"contact_name": "Org A Lead"}, headers=auth_headers)

    other_register = client.post(
        "/api/v1/auth/register",
        json={"organization_name": "Other Org", "email": "other-leads@example.com", "password": "password123"},
    )
    other_headers = {"Authorization": f"Bearer {other_register.json()['access_token']}"}

    listing = client.get("/api/v1/leads", headers=other_headers)
    assert listing.status_code == 200
    assert listing.json() == []


def test_leads_by_id_are_scoped_to_organization(client, auth_headers):
    # Create a lead as Org A
    create_response = client.post(
        "/api/v1/leads", json={"contact_name": "Org A Lead"}, headers=auth_headers
    )
    assert create_response.status_code == 201
    org_a_lead_id = create_response.json()["id"]
    original_data = create_response.json()

    # Register Org B
    other_register = client.post(
        "/api/v1/auth/register",
        json={
            "organization_name": "Other Org",
            "email": "other-leads-idor@example.com",
            "password": "password123",
        },
    )
    assert other_register.status_code == 201
    other_headers = {"Authorization": f"Bearer {other_register.json()['access_token']}"}

    # Test GET by ID: Org B should get 404
    get_response = client.get(f"/api/v1/leads/{org_a_lead_id}", headers=other_headers)
    assert get_response.status_code == 404
    assert get_response.json()["code"] == "not_found"

    # Test PATCH by ID: Org B should get 404
    patch_response = client.patch(
        f"/api/v1/leads/{org_a_lead_id}",
        json={"status": "qualified"},
        headers=other_headers,
    )
    assert patch_response.status_code == 404
    assert patch_response.json()["code"] == "not_found"

    # Test DELETE by ID: Org B should get 404
    delete_response = client.delete(f"/api/v1/leads/{org_a_lead_id}", headers=other_headers)
    assert delete_response.status_code == 404
    assert delete_response.json()["code"] == "not_found"

    # Verify Org A's lead still exists and is unchanged
    verify_response = client.get(f"/api/v1/leads/{org_a_lead_id}", headers=auth_headers)
    assert verify_response.status_code == 200
    assert verify_response.json()["id"] == org_a_lead_id
    assert verify_response.json()["status"] == original_data["status"]


def test_create_lead_with_email_sets_verified_from_check(client, auth_headers):
    with patch("app.api.routes.leads.verify_email", return_value=True):
        response = client.post(
            "/api/v1/leads",
            json={"contact_name": "Jane Doe", "email": "jane@example.com"},
            headers=auth_headers,
        )
    assert response.status_code == 201
    assert response.json()["email_verified"] is True


def test_update_lead_email_reverifies(client, auth_headers):
    create = client.post("/api/v1/leads", json={"contact_name": "Jane Doe"}, headers=auth_headers)
    lead_id = create.json()["id"]
    with patch("app.api.routes.leads.verify_email", return_value=False):
        response = client.patch(
            f"/api/v1/leads/{lead_id}", json={"email": "bad@nomx.example"}, headers=auth_headers
        )
    assert response.status_code == 200
    assert response.json()["email_verified"] is False
