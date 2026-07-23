def test_create_and_list_company(client, auth_headers):
    response = client.post(
        "/api/v1/companies", json={"name": "Acme Corp", "website": "https://acme.com"}, headers=auth_headers
    )
    assert response.status_code == 201
    company_id = response.json()["id"]

    listing = client.get("/api/v1/companies", headers=auth_headers)
    assert listing.status_code == 200
    assert len(listing.json()) == 1
    assert listing.json()[0]["id"] == company_id


def test_get_company_not_found(client, auth_headers):
    response = client.get(
        "/api/v1/companies/00000000-0000-0000-0000-000000000000", headers=auth_headers
    )
    assert response.status_code == 404
    assert response.json()["code"] == "not_found"


def test_update_company(client, auth_headers):
    create = client.post("/api/v1/companies", json={"name": "Acme Corp"}, headers=auth_headers)
    company_id = create.json()["id"]
    response = client.patch(
        f"/api/v1/companies/{company_id}", json={"industry": "Software"}, headers=auth_headers
    )
    assert response.status_code == 200
    assert response.json()["industry"] == "Software"


def test_delete_company(client, auth_headers):
    create = client.post("/api/v1/companies", json={"name": "Acme Corp"}, headers=auth_headers)
    company_id = create.json()["id"]
    response = client.delete(f"/api/v1/companies/{company_id}", headers=auth_headers)
    assert response.status_code == 204
    get_response = client.get(f"/api/v1/companies/{company_id}", headers=auth_headers)
    assert get_response.status_code == 404


def test_companies_are_scoped_to_organization(client, auth_headers):
    client.post("/api/v1/companies", json={"name": "Org A Co"}, headers=auth_headers)

    other_register = client.post(
        "/api/v1/auth/register",
        json={"organization_name": "Other Org", "email": "other@example.com", "password": "password123"},
    )
    other_headers = {"Authorization": f"Bearer {other_register.json()['access_token']}"}

    listing = client.get("/api/v1/companies", headers=other_headers)
    assert listing.status_code == 200
    assert listing.json() == []
