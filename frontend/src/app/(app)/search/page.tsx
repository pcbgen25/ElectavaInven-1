"use client";

import { useQuery } from "@tanstack/react-query";
import { Search } from "lucide-react";
import Link from "next/link";
import { useEffect, useState } from "react";

import { Input } from "@/components/ui/form";
import { EmptyState, ErrorState, LifecycleBadge, PageHeader, Spinner } from "@/components/ui/primitives";
import { api, type Paginated } from "@/lib/api";
import type { ComponentListItem } from "@/lib/types";

/** Mobile-first quick search across the component database. */
export default function SearchPage() {
  const [text, setText] = useState("");
  const [q, setQ] = useState("");
  useEffect(() => {
    const t = setTimeout(() => setQ(text.trim()), 300);
    return () => clearTimeout(t);
  }, [text]);

  const { data, isFetching, error } = useQuery<any>({
    queryKey: ["components", "quick-search", q],
    queryFn: () => api<Paginated<ComponentListItem>>("components", { query: { search: q, page_size: 30 } }),
    enabled: q.length >= 2,
  });

  return (
    <>
      <PageHeader title="Search" subtitle="Components by PN, MPN, manufacturer, package, alias or value" />
      <div className="relative mb-4">
        <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-400" />
        <Input autoFocus type="search" aria-label="Search components" placeholder="e.g. TCAN1042, 100nF, SOIC-8…" className="h-11 pl-9 text-base" value={text} onChange={(e) => setText(e.target.value)} />
      </div>
      {q.length < 2 ? <p className="text-sm text-slate-500">Type at least 2 characters.</p>
        : error ? <ErrorState message={(error as Error).message} />
        : isFetching && !data ? <Spinner />
        : !data?.results.length ? <EmptyState title="No components found" description={`Nothing matches “${q}”.`} />
        : (
          <ul className="divide-y divide-slate-100 rounded-lg border border-slate-200 bg-white">
            {data.results.map((c: any) => (
              <li key={c.id}>
                <Link href={`/components/${c.id}`} className="block px-3 py-2.5 hover:bg-slate-50">
                  <div className="flex items-center justify-between gap-2"><span className="pn font-medium text-blue-700">{c.internal_part_number}</span><LifecycleBadge value={c.lifecycle_status} /></div>
                  <div className="text-sm text-slate-900">{c.mpn || c.name}</div>
                  <div className="text-xs text-slate-500">{[c.mpn ? c.name : null, c.manufacturer?.name, c.package?.name].filter(Boolean).join(" · ")}</div>
                </Link>
              </li>
            ))}
            {data.count > data.results.length && (
              <li className="px-3 py-2 text-center text-sm"><Link className="text-blue-700 hover:underline" href={`/components?search=${encodeURIComponent(q)}`}>View all {data.count} results</Link></li>
            )}
          </ul>
        )}
    </>
  );
}
