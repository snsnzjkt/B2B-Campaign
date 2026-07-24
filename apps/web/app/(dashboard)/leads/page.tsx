"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { apiFetch } from "@/lib/api-client";

interface Lead {
  id: string;
  contact_name: string | null;
  email: string | null;
  status: string;
}

export default function LeadsPage() {
  const [leads, setLeads] = useState<Lead[] | null>(null);

  useEffect(() => {
    apiFetch<Lead[]>("/leads").then(setLeads);
  }, []);

  if (leads === null) {
    return <p className="text-neutral-500">Loading...</p>;
  }

  if (leads.length === 0) {
    return (
      <div className="rounded-lg border border-dashed border-neutral-300 bg-white p-12 text-center">
        <h2 className="text-lg font-medium text-neutral-900">No leads yet</h2>
        <p className="mt-2 text-sm text-neutral-500">Search for companies to import as leads.</p>
        <Link
          href="/leads/discover"
          className="mt-4 inline-block text-sm font-medium text-neutral-900 underline underline-offset-4"
        >
          Discover leads
        </Link>
      </div>
    );
  }

  return (
    <ul className="divide-y divide-neutral-200 rounded-lg border border-neutral-200 bg-white">
      {leads.map((lead) => (
        <li key={lead.id} className="px-4 py-3 text-sm text-neutral-900">
          {lead.contact_name ?? lead.email ?? "Unnamed lead"} — {lead.status}
        </li>
      ))}
    </ul>
  );
}
