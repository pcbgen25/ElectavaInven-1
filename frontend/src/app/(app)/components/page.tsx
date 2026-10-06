"use client";

import { keepPreviousData, useQuery } from "@tanstack/react-query";
import { Plus, X } from "lucide-react";
import Link from "next/link";

import { DataTable, type Column } from "@/components/data-table/data-table";
import { Button } from "@/components/ui/button";
import { Select } from "@/components/ui/form";
import { Badge, EmptyState, LifecycleBadge, PageHeader } from "@/components/ui/primitives";
import { api, fetchAllPages, type Paginated } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { categoryTreeOptions, useCategories, useManufacturerOptions, usePackageOptions } from "@/lib/queries";
import { LIFECYCLE_LABELS, STATUS_LABELS, type ComponentListItem } from "@/lib/types";
import { formatDateTime, triState } from "@/lib/utils";
import { useListState } from "@/lib/use-list-state";

const COLUMNS: Column<ComponentListItem>[] = [
  { key: "ipn", header: "Internal PN", sortKey: "internal_part_number", render: (c) => <span className="pn">{c.internal_part_number}</span>, csv: (c) => c.internal_part_number },
  { key: "mpn", header: "MPN", sortKey: "mpn", render: (c) => <span className="pn">{c.mpn || "—"}</span>, csv: (c) => c.mpn },
  { key: "name", header: "Name", sortKey: "name", render: (c) => <span className="text-slate-800">{c.name}</span>, csv: (c) => c.name },
  { key: "manufacturer", header: "Manufacturer", sortKey: "manufacturer__name", render: (c) => c.manufacturer?.name ?? "—", csv: (c) => c.manufacturer?.name },
  { key: "category", header: "Category", sortKey: "category__name", render: (c) => c.category.name, csv: (c) => c.category.name },
  { key: "package", header: "Package", sortKey: "package__name", render: (c) => c.package?.name ?? "—", csv: (c) => c.package?.name },
  { key: "lifecycle", header: "Lifecycle", sortKey: "lifecycle_status", render: (c) => <LifecycleBadge value={c.lifecycle_status} />, csv: (c) => LIFECYCLE_LABELS[c.lifecycle_status] },
  { key: "status", header: "Status", sortKey: "status", render: (c) => <Badge tone={c.status === "ACTIVE" ? "blue" : "slate"}>{STATUS_LABELS[c.status]}</Badge>, csv: (c) => STATUS_LABELS[c.status] },
  { key: "rohs", header: "RoHS", render: (c) => triState(c.is_rohs), csv: (c) => triState(c.is_rohs), hiddenByDefault: true },
  { key: "description", header: "Description", render: (c) => <span className="line-clamp-1 text-slate-500">{c.description}</span>, csv: (c) => c.description, hiddenByDefault: true },
  { key: "updated", header: "Updated", sortKey: "updated_at", render: (c) => <span className="whitespace-nowrap text-slate-500">{formatDateTime(c.updated_at)}</span>, csv: (c) => c.updated_at, hiddenByDefault: true },
];

function MobileCard({ c }: { c: ComponentListItem }) {
  return (
    <div className="space-y-1">
      <div className="flex items-center justify-between gap-2">
        <span className="pn font-medium text-blue-700">{c.internal_part_number}</span>
        <LifecycleBadge value={c.lifecycle_status} />
      </div>
      <div className="text-sm font-medium text-slate-900">{c.mpn || c.name}</div>
      <div className="text-xs text-slate-500">{[c.mpn ? c.name : null, c.manufacturer?.name, c.package?.name].filter(Boolean).join(" · ")}</div>
    </div>
  );
}

export default function ComponentsPage() {
  const { can } = useAuth();
  const list = useListState({ ordering: "internal_part_number" });
  const { data: categories } = useCategories();
  const { data: manufacturers } = useManufacturerOptions();
  const { data: packages } = usePackageOptions();

  const { data, isFetching, error, refetch } = useQuery<any>({
    queryKey: ["components", list.query],
    queryFn: () => api<Paginated<ComponentListItem>>("components", { query: list.query }),
    placeholderData: keepPreviousData,
  });

  const f = list.filters;
  const activeFilters = ["category", "manufacturer", "package", "status", "lifecycle_status"].filter((k) => f[k]);

  const filterSelect = (key: string, label: string, options: { value: string | number; label: string }[]) => (
    <Select aria-label={label} value={f[key] ?? ""} onChange={(e) => list.update({ [key]: e.target.value })} className="h-8 w-auto min-w-0 max-w-44 text-xs">
      <option value="">{label}: all</option>
      {options.map((o) => <option key={o.value} value={o.value}>{o.label}</option>)}
    </Select>
  );

  return (
    <>
      <PageHeader
        title="Components"
        subtitle="Master component database"
        actions={can("component.create") && <Link href="/components/new"><Button><Plus className="h-4 w-4" /> Add component</Button></Link>}
      />
      <DataTable
        id="components"
        exportName="components"
        columns={COLUMNS}
        rows={data?.results}
        count={data?.count ?? 0}
        page={list.page}
        pageSize={list.pageSize}
        ordering={list.ordering}
        loading={isFetching}
        error={error ? (error as Error).message : null}
        onRetry={() => refetch()}
        search={list.search}
        onSearch={(v) => list.update({ search: v })}
        searchPlaceholder="Search PN, MPN, manufacturer, package, alias, value (e.g. 100nF)…"
        onOrdering={(o) => list.update({ ordering: o })}
        onPage={(p) => list.update({ page: p }, false)}
        onPageSize={(s) => list.update({ page_size: s })}
        rowKey={(c) => c.id}
        rowHref={(c) => `/components/${c.id}`}
        mobileCard={(c) => <MobileCard c={c} />}
        onExport={() => fetchAllPages<ComponentListItem>("components", { ...list.query, page: undefined, page_size: undefined })}
        toolbar={
          <>
            {filterSelect("category", "Category", categoryTreeOptions(categories).map((o) => ({ value: o.id, label: o.label })))}
            {filterSelect("manufacturer", "Manufacturer", (manufacturers ?? []).map((m) => ({ value: m.id, label: m.name })))}
            {filterSelect("package", "Package", (packages ?? []).map((p) => ({ value: p.id, label: p.name })))}
            {filterSelect("lifecycle_status", "Lifecycle", Object.entries(LIFECYCLE_LABELS).map(([v, l]) => ({ value: v, label: l })))}
            {filterSelect("status", "Status", Object.entries(STATUS_LABELS).map(([v, l]) => ({ value: v, label: l })))}
            {activeFilters.length > 0 && (
              <Button variant="ghost" size="sm" onClick={() => list.update(Object.fromEntries(activeFilters.map((k) => [k, null])))}>
                <X className="h-3.5 w-3.5" /> Clear
              </Button>
            )}
          </>
        }
        empty={
          <EmptyState
            title={list.search || activeFilters.length ? "No components match" : "No components yet"}
            description={list.search ? `Nothing found for “${list.search}”. Search covers PN, MPN, manufacturer, package, aliases and specification values.` : undefined}
            action={can("component.create") && <Link href="/components/new"><Button size="sm"><Plus className="h-4 w-4" /> Add component</Button></Link>}
          />
        }
      />
    </>
  );
}
