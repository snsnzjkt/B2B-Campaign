"use client";

import { useState } from "react";
import { ApiError } from "@/lib/api-client";
import { type DiscoveryCandidate, importDiscoveryCandidates, searchDiscovery } from "@/lib/discovery";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Checkbox } from "@/components/ui/checkbox";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";

export default function DiscoverPage() {
  const [query, setQuery] = useState("");
  const [location, setLocation] = useState("");
  const [candidates, setCandidates] = useState<DiscoveryCandidate[] | null>(null);
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const [loading, setLoading] = useState(false);
  const [importing, setImporting] = useState(false);
  const [summary, setSummary] = useState<{ created: number; skipped_duplicate: number } | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function handleSearch(event: React.FormEvent) {
    event.preventDefault();
    setError(null);
    setSummary(null);
    setLoading(true);
    try {
      const response = await searchDiscovery(query, location);
      setCandidates(response.candidates);
      setSelected(new Set());
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Something went wrong");
    } finally {
      setLoading(false);
    }
  }

  function toggleSelected(externalId: string) {
    setSelected((prev) => {
      const next = new Set(prev);
      if (next.has(externalId)) {
        next.delete(externalId);
      } else {
        next.add(externalId);
      }
      return next;
    });
  }

  async function handleImport() {
    if (!candidates) return;
    const toImport = candidates.filter((c) => selected.has(c.external_id));
    if (toImport.length === 0) return;
    setError(null);
    setImporting(true);
    try {
      const response = await importDiscoveryCandidates(toImport);
      setSummary(response);
      setCandidates((prev) =>
        prev
          ? prev.map((c) => (selected.has(c.external_id) ? { ...c, already_imported: true } : c))
          : prev,
      );
      setSelected(new Set());
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Something went wrong");
    } finally {
      setImporting(false);
    }
  }

  return (
    <div className="space-y-6">
      <Card className="p-6">
        <h1 className="text-lg font-medium text-neutral-900">Discover leads</h1>
        <p className="mt-1 text-sm text-neutral-500">Search Google Places for companies to import as leads.</p>
        <form onSubmit={handleSearch} className="mt-4 flex flex-wrap items-end gap-3">
          <div className="space-y-1.5">
            <Label htmlFor="query">What</Label>
            <Input
              id="query"
              placeholder="marketing agencies"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              required
            />
          </div>
          <div className="space-y-1.5">
            <Label htmlFor="location">Where</Label>
            <Input
              id="location"
              placeholder="Denver, CO"
              value={location}
              onChange={(e) => setLocation(e.target.value)}
              required
            />
          </div>
          <Button type="submit" disabled={loading}>
            {loading ? "Searching…" : "Search"}
          </Button>
        </form>
        {error && <p className="mt-3 text-sm text-destructive">{error}</p>}
      </Card>

      {summary && (
        <div className="rounded-lg border border-neutral-200 bg-white px-4 py-3 text-sm text-neutral-700">
          Imported {summary.created} {summary.created === 1 ? "lead" : "leads"}
          {summary.skipped_duplicate > 0 &&
            ` (${summary.skipped_duplicate} skipped as ${
              summary.skipped_duplicate === 1 ? "duplicate" : "duplicates"
            })`}
          .
        </div>
      )}

      {candidates && (
        <div className="rounded-lg border border-neutral-200 bg-white">
          {candidates.length === 0 ? (
            <p className="p-6 text-sm text-neutral-500">No results.</p>
          ) : (
            <>
              <ul className="divide-y divide-neutral-200">
                {candidates.map((candidate) => (
                  <li key={candidate.external_id} className="flex items-center gap-3 px-4 py-3">
                    <Checkbox
                      checked={selected.has(candidate.external_id)}
                      disabled={candidate.already_imported}
                      onCheckedChange={() => toggleSelected(candidate.external_id)}
                    />
                    <div className="flex-1 text-sm">
                      <div className="font-medium text-neutral-900">{candidate.name}</div>
                      <div className="text-neutral-500">
                        {[candidate.address, candidate.phone, candidate.website].filter(Boolean).join(" · ")}
                      </div>
                    </div>
                    {candidate.already_imported && <Badge variant="outline">Already imported</Badge>}
                  </li>
                ))}
              </ul>
              <div className="border-t border-neutral-200 px-4 py-3">
                <Button onClick={handleImport} disabled={selected.size === 0 || importing}>
                  {importing ? "Importing…" : `Import selected (${selected.size})`}
                </Button>
              </div>
            </>
          )}
        </div>
      )}
    </div>
  );
}
