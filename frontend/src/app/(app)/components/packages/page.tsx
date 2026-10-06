"use client";

import { keepPreviousData, useQuery } from "@tanstack/react-query";
import { Pencil, Plus, Trash2 } from "lucide-react";
import Link from "next/link";
import { useState } from "react";

import { DataTable, type Column } from "@/components/data-table/data-table";
import { CrudModal, useDeleter, type FieldSpec } from "@/components/masterdata/crud-modal";
import { Button } from "@/components/ui/button";
import { Badge, EmptyState, PageHeader } from "@/components/ui/primitives";
import { api, fetchAllPages, type Paginated } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import type { Package } from "@/lib/types";
import { useListState } from "@/lib/use-list-state";

const MOUNTING = [{ value: "SMD", label: "SMD" }, { value: "THT", label: "Through-hole" }, { value: "OTHER", label: "Other" }];
const FIELDS: FieldSpec[] = [
  { name: "name", label: "Name", type: "text", required: true, placeholder: "e.g. SOIC-8" },
  { name: "mounting_type", label: "Mounting", type: "select", options: MOUNTING },
  { name: "pin_count", label: "Pin count", type: "number" },
  { name: "description", label: "Description", type: "textarea" },
];
const INVALIDATE = [["packages"], ["components"]];

export default function PackagesPage() {
  const { can } = useAuth();
  const canManage = can("masterdata.manage");
  const list = useListState({ ordering: "name" });
  const [editing, setEditing] = useState<Package | null | undefined>(undefined);
  const del = useDeleter(INVALIDATE);

  const { data, isFetching, error, refetch } = useQuery<any>({
    queryKey: ["packages", list.query],
    queryFn: () => api<Paginated<Package>>("packages", { query: list.query }),
    placeholderData: keepPreviousData,
  });

  const columns: Column<Package>[] = [
    { key: "name", header: "Name", sortKey: "name", render: (p) => <span className="pn font-medium text-slate-900">{p.name}</span>, csv: (p) => p.name },
    { key: "mount", header: "Mounting", render: (p) => <Badge tone={p.mounting_type === "SMD" ? "blue" : "violet"}>{p.mounting_type}</Badge>, csv: (p) => p.mounting_type },
    { key: "pins", header: "Pins", sortKey: "pin_count", render: (p) => p.pin_count ?? "—", csv: (p) => p.pin_count },
    { key: "desc", header: "Description", render: (p) => <span className="line-clamp-1 text-slate-500">{p.description}</span>, csv: (p) => p.description },
    { key: "count", header: "Components", sortKey: "component_count", render: (p) => <Link href={`/components?package=${p.id}`} className="text-blue-700 hover:underline">{p.component_count}</Link>, csv: (p) => p.component_count },
    ...(canManage ? [{
      key: "actions", header: "", render: (p: Package) => (
        <div className="flex justify-end gap-1">
          <Button size="sm" variant="ghost" aria-label={`Edit ${p.name}`} onClick={() => setEditing(p)}><Pencil className="h-3.5 w-3.5" /></Button>
          <Button size="sm" variant="ghost" aria-label={`Delete ${p.name}`} onClick={() => del(`packages/${p.id}`, p.name)}><Trash2 className="h-3.5 w-3.5" /></Button>
        </div>
      ),
    }] : []),
  ];

  return (
    <>
      <PageHeader title="Packages" subtitle="Component package / footprint types"
        actions={canManage && <Button onClick={() => setEditing(null)}><Plus className="h-4 w-4" /> Add package</Button>} />
      <DataTable
        id="packages" exportName="packages" columns={columns} rows={data?.results} count={data?.count ?? 0}
        page={list.page} pageSize={list.pageSize} ordering={list.ordering} loading={isFetching}
        error={error ? (error as Error).message : null} onRetry={() => refetch()}
        search={list.search} onSearch={(v) => list.update({ search: v })} searchPlaceholder="Search packages…"
        onOrdering={(o) => list.update({ ordering: o })} onPage={(p) => list.update({ page: p }, false)} onPageSize={(s) => list.update({ page_size: s })}
        rowKey={(p) => p.id}
        mobileCard={(p) => (
          <div className="flex items-center justify-between gap-2">
            <div><div className="pn font-medium text-slate-900">{p.name}</div><div className="text-xs text-slate-500">{p.mounting_type}{p.pin_count ? ` · ${p.pin_count} pins` : ""}</div></div>
            <div className="flex items-center gap-1 text-xs text-slate-500">{p.component_count} parts
              {canManage && <Button size="sm" variant="ghost" aria-label="Edit" onClick={() => setEditing(p)}><Pencil className="h-3.5 w-3.5" /></Button>}
            </div>
          </div>
        )}
        onExport={() => fetchAllPages<Package>("packages", { ...list.query, page: undefined, page_size: undefined })}
        empty={<EmptyState title="No packages" />}
      />
      <CrudModal open={editing !== undefined} onClose={() => setEditing(undefined)} title={editing ? `Edit ${editing.name}` : "Add package"}
        endpoint="packages" id={editing?.id} fields={FIELDS} initial={editing ?? { mounting_type: "SMD" }} invalidate={INVALIDATE} />
    </>
  );
}
