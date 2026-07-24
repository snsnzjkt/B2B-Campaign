from unittest.mock import Mock, patch

from app.providers.google_places import GooglePlacesProvider

FAKE_RESPONSE = {
    "places": [
        {
            "id": "place-123",
            "displayName": {"text": "Acme Corp"},
            "formattedAddress": "123 Main St, Denver, CO",
            "websiteUri": "https://acme.com",
            "internationalPhoneNumber": "+1 303-555-0100",
        }
    ]
}


def test_search_maps_places_response_to_discovered_companies():
    mock_response = Mock()
    mock_response.json.return_value = FAKE_RESPONSE
    mock_response.raise_for_status.return_value = None

    with patch("app.providers.google_places.requests.post", return_value=mock_response) as mock_post:
        results = GooglePlacesProvider().search("marketing agencies", "Denver, CO")

    assert len(results) == 1
    assert results[0].name == "Acme Corp"
    assert results[0].website == "https://acme.com"
    assert results[0].phone == "+1 303-555-0100"
    assert results[0].address == "123 Main St, Denver, CO"
    assert results[0].external_id == "place-123"
    mock_post.assert_called_once()


def test_search_handles_missing_optional_fields():
    mock_response = Mock()
    mock_response.json.return_value = {
        "places": [{"id": "place-456", "displayName": {"text": "No Site LLC"}}]
    }
    mock_response.raise_for_status.return_value = None

    with patch("app.providers.google_places.requests.post", return_value=mock_response):
        results = GooglePlacesProvider().search("agencies", "Denver, CO")

    assert results[0].website is None
    assert results[0].phone is None
    assert results[0].address is None


def test_search_empty_results():
    mock_response = Mock()
    mock_response.json.return_value = {}
    mock_response.raise_for_status.return_value = None

    with patch("app.providers.google_places.requests.post", return_value=mock_response):
        results = GooglePlacesProvider().search("agencies", "Nowhere")

    assert results == []
