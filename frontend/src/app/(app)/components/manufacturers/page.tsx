"use client";

import { keepPreviousData, useQuery } from "@tanstack/react-query";
import { Pencil, Plus, Trash2 } from "lucide-react";
import Link from "next/link";
import { useState } from "react";

import { DataTable, type Column } from "@/components/data-table/data-table";
import { CrudModal, useDeleter, type FieldSpec } from "@/components/masterdata/crud-modal";
import { Button } from "@/components/ui/button";
import { EmptyState, PageHeader } from "@/components/ui/primitives";
import { api, fetchAllPages, type Paginated } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import type { Manufacturer } from "@/lib/types";
import { useListState } from "@/lib/use-list-state";

const FIELDS: FieldSpec[] = [
  { name: "name", label: "Name", type: "text", required: true, placeholder: "e.g. Texas Instruments" },
  { name: "short_name", label: "Short name", type: "text", placeholder: "e.g. TI" },
  { name: "website", label: "Website", type: "url", placeholder: "https://…" },
  { name: "country", label: "Country", type: "text" },
  { name: "notes", label: "Notes", type: "textarea" },
];
const INVALIDATE = [["manufacturers"], ["components"]];

export default function ManufacturersPage() {
  const { can } = useAuth();
  const canManage = can("masterdata.manage");
  const list = useListState({ ordering: "name" });
  const [editing, setEditing] = useState<Manufacturer | null | undefined>(undefined);
  const del = useDeleter(INVALIDATE);

  const { data, isFetching, error, refetch } = useQuery<any>({
    queryKey: ["manufacturers", list.query],
    queryFn: () => api<Paginated<Manufacturer>>("manufacturers", { query: list.query }),
    placeholderData: keepPreviousData,
  });

  const columns: Column<Manufacturer>[] = [
    { key: "name", header: "Name", sortKey: "name", render: (m) => <span className="font-medium text-slate-900">{m.name}</span>, csv: (m) => m.name },
    { key: "short", header: "Short", render: (m) => m.short_name || "—", csv: (m) => m.short_name },
    { key: "country", header: "Country", sortKey: "country", render: (m) => m.country || "—", csv: (m) => m.country },
    { key: "website", header: "Website", render: (m) => m.website ? <a href={m.website} target="_blank" rel="noopener noreferrer" onClick={(e) => e.stopPropagation()} className="text-blue-700 hover:underline">{m.website.replace(/^https?:\/\//, "")}</a> : "—", csv: (m) => m.website },
    { key: "count", header: "Components", sortKey: "component_count", render: (m) => <Link href={`/components?manufacturer=${m.id}`} className="text-blue-700 hover:underline">{m.component_count}</Link>, csv: (m) => m.component_count },
    ...(canManage ? [{
      key: "actions", header: "", render: (m: Manufacturer) => (
        <div className="flex justify-end gap-1">
          <Button size="sm" variant="ghost" aria-label={`Edit ${m.name}`} onClick={() => setEditing(m)}><Pencil className="h-3.5 w-3.5" /></Button>
          <Button size="sm" variant="ghost" aria-label={`Delete ${m.name}`} onClick={() => del(`manufacturers/${m.id}`, m.name)}><Trash2 className="h-3.5 w-3.5" /></Button>
        </div>
      ),
    }] : []),
  ];

  return (
    <>
      <PageHeader title="Manufacturers" subtitle="Component manufacturers"
        actions={canManage && <Button onClick={() => setEditing(null)}><Plus className="h-4 w-4" /> Add manufacturer</Button>} />
      <DataTable
        id="manufacturers" exportName="manufacturers" columns={columns} rows={data?.results} count={data?.count ?? 0}
        page={list.page} pageSize={list.pageSize} ordering={list.ordering} loading={isFetching}
        error={error ? (error as Error).message : null} onRetry={() => refetch()}
        search={list.search} onSearch={(v) => list.update({ search: v })} searchPlaceholder="Search name, short name, country…"
        onOrdering={(o) => list.update({ ordering: o })} onPage={(p) => list.update({ page: p }, false)} onPageSize={(s) => list.update({ page_size: s })}
        rowKey={(m) => m.id}
        mobileCard={(m) => (
          <div className="flex items-center justify-between gap-2">
            <div><div className="font-medium text-slate-900">{m.name}</div><div className="text-xs text-slate-500">{[m.short_name, m.country].filter(Boolean).join(" · ")}</div></div>
            <div className="flex items-center gap-1 text-xs text-slate-500">{m.component_count} parts
              {canManage && <Button size="sm" variant="ghost" aria-label="Edit" onClick={() => setEditing(m)}><Pencil className="h-3.5 w-3.5" /></Button>}
            </div>
          </div>
        )}
        onExport={() => fetchAllPages<Manufacturer>("manufacturers", { ...list.query, page: undefined, page_size: undefined })}
        empty={<EmptyState title="No manufacturers" />}
      />
      <CrudModal open={editing !== undefined} onClose={() => setEditing(undefined)} title={editing ? `Edit ${editing.name}` : "Add manufacturer"}
        endpoint="manufacturers" id={editing?.id} fields={FIELDS} initial={editing ?? undefined} invalidate={INVALIDATE} />
    </>
  );
}
