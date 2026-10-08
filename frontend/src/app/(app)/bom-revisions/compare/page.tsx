"use client";
import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { useSearchParams } from "next/navigation";
import { Button } from "@/components/ui/button";
import { DataTable } from "@/components/ui/data-table";
import { ErrorState, Spinner } from "@/components/ui/primitives";
import { api } from "@/lib/api";

export default function ComparePage() {
  const searchParams = useSearchParams();
  const bomId = searchParams.get("bom");
  
  const [revA, setRevA] = useState("");
  const [revB, setRevB] = useState("");

  const { data: bom } = useQuery<any>({
    queryKey: ["boms", bomId],
    queryFn: () => api(`/boms/${bomId}/`),
    enabled: !!bomId
  });

  const { data: diffs, isLoading, refetch } = useQuery<any>({
    queryKey: ["bom_compare", revA, revB],
    queryFn: () => api(`/bom-revisions/compare/?rev_a=${revA}&rev_b=${revB}`),
    enabled: false
  });

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold text-slate-900 dark:text-white">Compare BOM Revisions</h1>
      
      <div className="flex items-end gap-4 bg-white dark:bg-zinc-950 p-4 rounded-xl border dark:border-zinc-800">
        <div className="flex-1">
          <label className="block text-sm font-medium mb-1 dark:text-zinc-300">Revision A (Base)</label>
          <select className="w-full p-2 border rounded dark:bg-zinc-900 dark:border-zinc-700 dark:text-white" value={revA} onChange={(e) => setRevA(e.target.value)}>
            <option value="">Select...</option>
            {bom?.revisions?.map((r: any) => <option key={r.id} value={r.id}>{r.revision_number}</option>)}
          </select>
        </div>
        <div className="flex-1">
          <label className="block text-sm font-medium mb-1 dark:text-zinc-300">Revision B (Target)</label>
          <select className="w-full p-2 border rounded dark:bg-zinc-900 dark:border-zinc-700 dark:text-white" value={revB} onChange={(e) => setRevB(e.target.value)}>
            <option value="">Select...</option>
            {bom?.revisions?.map((r: any) => <option key={r.id} value={r.id}>{r.revision_number}</option>)}
          </select>
        </div>
        <Button onClick={() => refetch()} disabled={!revA || !revB}>Compare</Button>
      </div>

      {isLoading && <Spinner />}
      {diffs?.diff && (
        <DataTable
          columns={[
            { header: "Component ID", accessorKey: "component_id" },
            { header: "Status", accessorKey: "status", cell: (r: any) => {
              const colors: Record<string,string> = {
                "ADDED": "text-emerald-600 bg-emerald-100 dark:bg-emerald-900/30",
                "REMOVED": "text-red-600 bg-red-100 dark:bg-red-900/30",
                "QUANTITY CHANGED": "text-amber-600 bg-amber-100 dark:bg-amber-900/30",
                "UNCHANGED": "text-slate-500 bg-slate-100 dark:bg-zinc-800"
              };
              return <span className={`px-2 py-1 rounded text-xs font-bold ${colors[r.status] || colors.UNCHANGED}`}>{r.status}</span>
            }},
            { header: "Qty A", accessorKey: "quantity_a" },
            { header: "Qty B", accessorKey: "quantity_b" },
            { header: "Designators A", accessorKey: "designators_a", cell: (r: any) => r.designators_a.join(", ") },
            { header: "Designators B", accessorKey: "designators_b", cell: (r: any) => r.designators_b.join(", ") },
          ]}
          data={diffs.diff}
        />
      )}
    </div>
  );
}
