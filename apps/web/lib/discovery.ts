import { apiFetch } from "./api-client";

export interface DiscoveryCandidate {
  name: string;
  website: string | null;
  phone: string | null;
  address: string | null;
  external_id: string;
  already_imported: boolean;
}

export interface DiscoverySearchResponse {
  candidates: DiscoveryCandidate[];
}

export interface DiscoveryImportResponse {
  created: number;
  skipped_duplicate: number;
}

export async function searchDiscovery(query: string, location: string): Promise<DiscoverySearchResponse> {
  return apiFetch<DiscoverySearchResponse>("/discovery/search", {
    method: "POST",
    body: JSON.stringify({ query, location }),
  });
}

export async function importDiscoveryCandidates(
  candidates: DiscoveryCandidate[],
): Promise<DiscoveryImportResponse> {
  return apiFetch<DiscoveryImportResponse>("/discovery/import", {
    method: "POST",
    body: JSON.stringify({ candidates }),
  });
}
