import requests

from app.config import settings
from app.providers.base import DiscoveredCompany, LeadDiscoveryProvider

PLACES_SEARCH_URL = "https://places.googleapis.com/v1/places:searchText"
FIELD_MASK = (
    "places.id,places.displayName,places.formattedAddress,"
    "places.websiteUri,places.internationalPhoneNumber"
)


class GooglePlacesProvider(LeadDiscoveryProvider):
    def search(self, query: str, location: str) -> list[DiscoveredCompany]:
        response = requests.post(
            PLACES_SEARCH_URL,
            json={"textQuery": f"{query} in {location}"},
            headers={
                "X-Goog-Api-Key": settings.google_places_api_key,
                "X-Goog-FieldMask": FIELD_MASK,
                "Content-Type": "application/json",
            },
            timeout=10,
        )
        response.raise_for_status()
        data = response.json()
        return [
            DiscoveredCompany(
                name=place.get("displayName", {}).get("text", ""),
                website=place.get("websiteUri"),
                phone=place.get("internationalPhoneNumber"),
                address=place.get("formattedAddress"),
                external_id=place["id"],
            )
            for place in data.get("places", [])
        ]
