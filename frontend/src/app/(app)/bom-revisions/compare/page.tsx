"use client";

import { useQuery } from "@tanstack/react-query";
import { useSearchParams } from "next/navigation";
import { useState } from "react";

import { Button } from "@/components/ui/button";
import { DataTable } from "@/components/ui/data-table";
import { Spinner } from "@/components/ui/primitives";
import { api, type Paginated } from "@/lib/api";
import type { BOM, BOMRevision } from "@/lib/types";

interface DiffRow {
  component_id: number;
  status: string;
  quantity_a: string | number | null;
  quantity_b: string | number | null;
  designators_a: string[];
  designators_b: string[];
}

export default function ComparePage() {
  const searchParams = useSearchParams();
  const initialBomId = searchParams.get("bom") || "";
  const [selectedBomId, setSelectedBomId] = useState(initialBomId);
  const [revA, setRevA] = useState("");
  const [revB, setRevB] = useState("");

  const { data: boms } = useQuery<Paginated<BOM>>({
    queryKey: ["boms", "all"],
    queryFn: () => api<Paginated<BOM>>("boms/"),
  });

  const activeBomId = selectedBomId || initialBomId;

  const { data: bom } = useQuery<BOM>({
    queryKey: ["boms", activeBomId],
    queryFn: () => api<BOM>(`boms/${activeBomId}/`),
    enabled: !!activeBomId,
  });

  const { data: diffs, isLoading, refetch } = useQuery<{ diff: DiffRow[] }>({
    queryKey: ["bom_compare", revA, revB],
    queryFn: () => api<{ diff: DiffRow[] }>(`bom-revisions/compare/?rev_a=${revA}&rev_b=${revB}`),
    enabled: false,
  });

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold text-slate-900 dark:text-white">Compare BOM Revisions</h1>

      <div className="grid grid-cols-1 gap-4 rounded-xl border bg-white p-4 sm:grid-cols-4 dark:border-zinc-800 dark:bg-zinc-950">
        <div>
          <label className="mb-1 block text-sm font-medium dark:text-zinc-300">BOM</label>
          <select
            className="w-full rounded border p-2 dark:border-zinc-700 dark:bg-zinc-900 dark:text-white"
            value={activeBomId}
            onChange={(e) => {
              setSelectedBomId(e.target.value);
              setRevA("");
              setRevB("");
            }}
          >
            <option value="">Select BOM...</option>
            {boms?.results?.map((b) => (
              <option key={b.id} value={b.id}>
                {b.name}
              </option>
            ))}
          </select>
        </div>
        <div>
          <label className="mb-1 block text-sm font-medium dark:text-zinc-300">Revision A (Base)</label>
          <select
            className="w-full rounded border p-2 dark:border-zinc-700 dark:bg-zinc-900 dark:text-white"
            value={revA}
            onChange={(e) => setRevA(e.target.value)}
          >
            <option value="">Select...</option>
            {bom?.revisions?.map((r: BOMRevision) => (
              <option key={r.id} value={r.id}>
                {r.revision_number}
              </option>
            ))}
          </select>
        </div>
        <div>
          <label className="mb-1 block text-sm font-medium dark:text-zinc-300">Revision B (Target)</label>
          <select
            className="w-full rounded border p-2 dark:border-zinc-700 dark:bg-zinc-900 dark:text-white"
            value={revB}
            onChange={(e) => setRevB(e.target.value)}
          >
            <option value="">Select...</option>
            {bom?.revisions?.map((r: BOMRevision) => (
              <option key={r.id} value={r.id}>
                {r.revision_number}
              </option>
            ))}
          </select>
        </div>
        <div className="flex items-end">
          <Button onClick={() => refetch()} disabled={!revA || !revB} className="w-full">
            Compare
          </Button>
        </div>
      </div>

      {isLoading && <Spinner />}
      {diffs?.diff && (
        <DataTable
          columns={[
            { header: "Component ID", accessorKey: "component_id" },
            {
              header: "Status",
              accessorKey: "status",
              cell: (r: DiffRow) => {
                const colors: Record<string, string> = {
                  ADDED: "text-emerald-600 bg-emerald-100 dark:bg-emerald-900/30",
                  REMOVED: "text-red-600 bg-red-100 dark:bg-red-900/30",
                  "QUANTITY CHANGED": "text-amber-600 bg-amber-100 dark:bg-amber-900/30",
                  UNCHANGED: "text-slate-500 bg-slate-100 dark:bg-zinc-800",
                };
                return <span className={`rounded px-2 py-1 text-xs font-bold ${colors[r.status] || colors.UNCHANGED}`}>{r.status}</span>;
              },
            },
            { header: "Qty A", accessorKey: "quantity_a" },
            { header: "Qty B", accessorKey: "quantity_b" },
            { header: "Designators A", accessorKey: "designators_a", cell: (r: DiffRow) => (r.designators_a || []).join(", ") },
            { header: "Designators B", accessorKey: "designators_b", cell: (r: DiffRow) => (r.designators_b || []).join(", ") },
          ]}
          data={diffs.diff}
        />
      )}
    </div>
  );
}
