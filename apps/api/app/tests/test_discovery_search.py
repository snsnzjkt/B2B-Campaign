from unittest.mock import patch

import requests

from app.providers.base import DiscoveredCompany

FAKE_RESULTS = [
    DiscoveredCompany(
        name="Acme Corp",
        website="https://acme.com",
        phone="+1 303-555-0100",
        address="123 Main St, Denver, CO",
        external_id="place-1",
    ),
    DiscoveredCompany(
        name="Other Co",
        website="https://other.com",
        phone=None,
        address="456 Elm St, Denver, CO",
        external_id="place-2",
    ),
]


def test_search_returns_candidates(client, auth_headers):
    with patch("app.api.routes.discovery.GooglePlacesProvider.search", return_value=FAKE_RESULTS):
        response = client.post(
            "/api/v1/discovery/search",
            json={"query": "marketing agencies", "location": "Denver, CO"},
            headers=auth_headers,
        )
    assert response.status_code == 200
    candidates = response.json()["candidates"]
    assert len(candidates) == 2
    assert all(c["already_imported"] is False for c in candidates)


def test_search_marks_already_imported_company(client, auth_headers):
    client.post(
        "/api/v1/companies",
        json={"name": "Acme Corp", "website": "https://acme.com"},
        headers=auth_headers,
    )
    with patch("app.api.routes.discovery.GooglePlacesProvider.search", return_value=FAKE_RESULTS):
        response = client.post(
            "/api/v1/discovery/search",
            json={"query": "marketing agencies", "location": "Denver, CO"},
            headers=auth_headers,
        )
    candidates = {c["external_id"]: c for c in response.json()["candidates"]}
    assert candidates["place-1"]["already_imported"] is True
    assert candidates["place-2"]["already_imported"] is False


def test_search_enforces_monthly_cap(client, auth_headers, monkeypatch):
    from app.config import settings

    monkeypatch.setattr(settings, "discovery_search_monthly_cap", 1)
    with patch("app.api.routes.discovery.GooglePlacesProvider.search", return_value=[]):
        first = client.post(
            "/api/v1/discovery/search",
            json={"query": "agencies", "location": "Denver, CO"},
            headers=auth_headers,
        )
        assert first.status_code == 200

        second = client.post(
            "/api/v1/discovery/search",
            json={"query": "agencies", "location": "Denver, CO"},
            headers=auth_headers,
        )
    assert second.status_code == 429
    assert second.json()["code"] == "rate_limit_exceeded"


def test_search_cap_is_scoped_per_organization(client, auth_headers, monkeypatch):
    from app.config import settings

    monkeypatch.setattr(settings, "discovery_search_monthly_cap", 1)
    with patch("app.api.routes.discovery.GooglePlacesProvider.search", return_value=[]):
        client.post(
            "/api/v1/discovery/search",
            json={"query": "agencies", "location": "Denver, CO"},
            headers=auth_headers,
        )

        other_register = client.post(
            "/api/v1/auth/register",
            json={
                "organization_name": "Other Org",
                "email": "other-discovery@example.com",
                "password": "password123",
            },
        )
        other_headers = {"Authorization": f"Bearer {other_register.json()['access_token']}"}

        response = client.post(
            "/api/v1/discovery/search",
            json={"query": "agencies", "location": "Denver, CO"},
            headers=other_headers,
        )
    assert response.status_code == 200


def test_search_returns_structured_error_when_provider_fails(client, auth_headers):
    with patch(
        "app.api.routes.discovery.GooglePlacesProvider.search",
        side_effect=requests.HTTPError("Google Places API error"),
    ):
        response = client.post(
            "/api/v1/discovery/search",
            json={"query": "agencies", "location": "Denver, CO"},
            headers=auth_headers,
        )
    assert response.status_code == 502
    assert response.json()["code"] == "provider_unavailable"
