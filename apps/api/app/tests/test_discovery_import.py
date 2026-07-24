from app.models import Company, Lead


def _candidate(**overrides):
    base = {
        "name": "Acme Corp",
        "website": "https://acme.com",
        "phone": "+1 303-555-0100",
        "address": "123 Main St, Denver, CO",
        "external_id": "place-1",
        "already_imported": False,
    }
    base.update(overrides)
    return base


def test_import_creates_company_and_lead(client, auth_headers, db_session):
    payload = {"candidates": [_candidate()]}
    response = client.post("/api/v1/discovery/import", json=payload, headers=auth_headers)
    assert response.status_code == 200
    assert response.json() == {"created": 1, "skipped_duplicate": 0}

    company = db_session.query(Company).filter_by(external_id="place-1").one()
    assert company.name == "Acme Corp"
    assert company.source == "google_places"

    lead = db_session.query(Lead).filter_by(company_id=company.id).one()
    assert lead.status == "new"
    assert lead.contact_name is None
    assert lead.email is None


def test_import_skips_existing_duplicate(client, auth_headers):
    client.post(
        "/api/v1/companies", json={"name": "Acme Corp", "website": "https://acme.com"}, headers=auth_headers
    )
    payload = {"candidates": [_candidate(website="https://acme.com")]}
    response = client.post("/api/v1/discovery/import", json=payload, headers=auth_headers)
    assert response.status_code == 200
    assert response.json() == {"created": 0, "skipped_duplicate": 1}


def test_import_is_scoped_to_organization(client, auth_headers):
    other_register = client.post(
        "/api/v1/auth/register",
        json={
            "organization_name": "Other Org",
            "email": "other-import@example.com",
            "password": "password123",
        },
    )
    other_headers = {"Authorization": f"Bearer {other_register.json()['access_token']}"}

    payload = {"candidates": [_candidate()]}
    client.post("/api/v1/discovery/import", json=payload, headers=other_headers)

    response = client.post("/api/v1/discovery/import", json=payload, headers=auth_headers)
    assert response.status_code == 200
    assert response.json() == {"created": 1, "skipped_duplicate": 0}
