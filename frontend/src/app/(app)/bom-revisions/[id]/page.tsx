"use client";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { useParams } from "next/navigation";
import { Button } from "@/components/ui/button";
import { DataTable } from "@/components/ui/data-table";
import { ErrorState, Spinner } from "@/components/ui/primitives";
import { api } from "@/lib/api";
import { BOMRevision } from "@/lib/types";
import { Lock, CheckCircle } from "lucide-react";
import { toast } from "sonner";

export default function RevDetail() {
  const params = useParams();
  const qc = useQueryClient();
  const revId = params.id;
  
  const { data: rev, isLoading } = useQuery<BOMRevision>({
    queryKey: ["bom_revision", revId],
    queryFn: () => api(`/bom-revisions/${revId}/`),
  });

  const releaseMut = useMutation({
    mutationFn: () => api(`/bom-revisions/${revId}/release/`, { method: "POST" }),
    onSuccess: () => {
      toast.success("BOM Released Successfully!");
      qc.invalidateQueries({ queryKey: ["bom_revision", revId] });
    },
    onError: () => toast.error("Failed to release BOM. Check permissions."),
  });

  if (isLoading) return <div className="mt-10 flex justify-center"><Spinner /></div>;
  if (!rev) return <ErrorState message="Failed to load Revision." />;

  const totalCost = rev.items.reduce((acc, it) => acc + (Number(it.total_cost_snapshot) || 0), 0);

  return (
    <div className="space-y-6">
      <div className="flex justify-between items-start bg-white p-6 rounded-xl border border-slate-200 dark:bg-zinc-950 dark:border-zinc-800 shadow-sm">
        <div>
          <h1 className="text-3xl font-bold text-slate-900 dark:text-white">{rev.revision_number}</h1>
          <p className="text-slate-500 mt-1">Status: <span className="font-semibold">{rev.status}</span></p>
        </div>
        <div>
          {rev.status === "RELEASED" ? (
            <div className="flex items-center text-blue-600 dark:text-blue-400 bg-blue-50 dark:bg-blue-900/30 px-4 py-2 rounded-lg border border-blue-200 dark:border-blue-800">
              <Lock className="w-5 h-5 mr-2" />
              <span className="font-bold">LOCKED & RELEASED</span>
            </div>
          ) : (
            <Button onClick={() => { if(confirm("Release Revision? It will become immutable.")) releaseMut.mutate(); }} loading={releaseMut.isPending} className="bg-blue-600 hover:bg-blue-700 text-white">
              <CheckCircle className="w-4 h-4 mr-2" /> Release BOM
            </Button>
          )}
        </div>
      </div>
      
      <div className="flex justify-between items-center px-2">
        <h2 className="text-xl font-semibold text-slate-900 dark:text-white">Items ({rev.items.length})</h2>
        <div className="text-lg font-bold text-emerald-600">Total Est Cost: ${totalCost.toFixed(2)}</div>
      </div>

      <DataTable
        columns={[
          { header: "Component", accessorKey: "component_details.internal_part_number" },
          { header: "Designators", accessorKey: "designators", cell: (r: any) => r.designators.join(", ") },
          { header: "Quantity", accessorKey: "quantity" },
          { header: "Unit Cost", accessorKey: "unit_cost_snapshot", cell: (r: any) => `$${Number(r.unit_cost_snapshot||0).toFixed(2)}` },
          { header: "Total", accessorKey: "total_cost_snapshot", cell: (r: any) => `$${Number(r.total_cost_snapshot||0).toFixed(2)}` },
        ]}
        data={rev.items}
      />
    </div>
  );
}
