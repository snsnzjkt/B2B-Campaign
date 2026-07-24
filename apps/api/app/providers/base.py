from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass
class DiscoveredCompany:
    name: str
    website: str | None
    phone: str | None
    address: str | None
    external_id: str


class LeadDiscoveryProvider(ABC):
    @abstractmethod
    def search(self, query: str, location: str) -> list[DiscoveredCompany]: ...
