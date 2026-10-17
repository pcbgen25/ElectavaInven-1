"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { CheckCircle, Lock } from "lucide-react";
import { useParams } from "next/navigation";
import { useState } from "react";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import { DataTable } from "@/components/ui/data-table";
import { Badge, ErrorState, Spinner } from "@/components/ui/primitives";
import { api } from "@/lib/api";
import type { BOMItem, BOMRevision } from "@/lib/types";

interface AvailabilityItem {
  component_id: number;
  internal_part_number: string;
  mpn: string;
  name: string;
  bom_lines: number;
  quantity_per_board: string;
  required: string;
  on_hand: string;
  reserved: string;
  available: string;
  shortage: string;
  status: "SHORTAGE" | "SUFFICIENT";
}

interface AvailabilityResponse {
  bom_revision: number;
  revision_status: string;
  build_quantity: string;
  components: number;
  components_short: number;
  items: AvailabilityItem[];
}

export default function RevDetail() {
  const params = useParams();
  const qc = useQueryClient();
  const revId = String(params.id || "");
  const [buildQty, setBuildQty] = useState(1);

  const { data: rev, isLoading } = useQuery<BOMRevision>({
    queryKey: ["bom_revision", revId],
    queryFn: () => api<BOMRevision>(`bom-revisions/${revId}/`),
  });

  const { data: availability } = useQuery<AvailabilityResponse>({
    queryKey: ["bom_revision_availability", revId, buildQty],
    queryFn: () => api<AvailabilityResponse>(`bom-revisions/${revId}/availability/`, { query: { build_quantity: buildQty } }),
    enabled: !!revId && buildQty > 0,
  });

  const releaseMut = useMutation({
    mutationFn: () => api(`bom-revisions/${revId}/release/`, { method: "POST" }),
    onSuccess: () => {
      toast.success("BOM Released Successfully!");
      qc.invalidateQueries({ queryKey: ["bom_revision", revId] });
    },
    onError: () => toast.error("Failed to release BOM. Check permissions."),
  });

  if (isLoading)
    return (
      <div className="mt-10 flex justify-center">
        <Spinner />
      </div>
    );
  if (!rev) return <ErrorState message="Failed to load Revision." />;

  const totalCost = rev.items.reduce((acc, it) => acc + (Number(it.total_cost_snapshot) || 0), 0);

  return (
    <div className="space-y-6">
      <div className="flex items-start justify-between rounded-xl border border-slate-200 bg-white p-6 shadow-sm dark:border-zinc-800 dark:bg-zinc-950">
        <div>
          <h1 className="text-3xl font-bold text-slate-900 dark:text-white">{rev.revision_number}</h1>
          <p className="mt-1 text-slate-500">
            Status: <span className="font-semibold">{rev.status}</span>
          </p>
        </div>
        <div>
          {rev.status === "RELEASED" ? (
            <div className="flex items-center rounded-lg border border-blue-200 bg-blue-50 px-4 py-2 text-blue-600 dark:border-blue-800 dark:bg-blue-900/30 dark:text-blue-400">
              <Lock className="mr-2 h-5 w-5" />
              <span className="font-bold">LOCKED & RELEASED</span>
            </div>
          ) : (
            <Button
              onClick={() => {
                if (confirm("Release Revision? It will become immutable.")) releaseMut.mutate();
              }}
              loading={releaseMut.isPending}
              className="bg-blue-600 text-white hover:bg-blue-700"
            >
              <CheckCircle className="mr-2 h-4 w-4" /> Release BOM
            </Button>
          )}
        </div>
      </div>

      <div className="flex items-center justify-between px-2">
        <h2 className="text-xl font-semibold text-slate-900 dark:text-white">Items ({rev.items.length})</h2>
        <div className="text-lg font-bold text-emerald-600">Total Est Cost: ${totalCost.toFixed(2)}</div>
      </div>

      <DataTable
        columns={[
          { header: "Component", accessorKey: "component_details.internal_part_number" },
          { header: "Designators", accessorKey: "designators", cell: (r: BOMItem) => r.designators.join(", ") },
          { header: "Quantity", accessorKey: "quantity" },
          {
            header: "Unit Cost",
            accessorKey: "unit_cost_snapshot",
            cell: (r: BOMItem) => `$${Number(r.unit_cost_snapshot || 0).toFixed(2)}`,
          },
          {
            header: "Total",
            accessorKey: "total_cost_snapshot",
            cell: (r: BOMItem) => `$${Number(r.total_cost_snapshot || 0).toFixed(2)}`,
          },
        ]}
        data={rev.items}
      />

      {availability && (
        <div className="space-y-4 pt-4">
          <div className="flex flex-wrap items-center justify-between gap-4 px-2">
            <div>
              <h2 className="text-xl font-semibold text-slate-900 dark:text-white">Stock Availability Check</h2>
              <p className="text-sm text-slate-500">
                {availability.components_short > 0
                  ? `${availability.components_short} of ${availability.components} components have a stock shortage.`
                  : "All components have sufficient available stock."}
              </p>
            </div>
            <div className="flex items-center gap-2">
              <label htmlFor="build-qty" className="text-sm font-medium text-slate-700 dark:text-slate-300">
                Build Quantity:
              </label>
              <input
                id="build-qty"
                type="number"
                min={1}
                value={buildQty}
                onChange={(e) => setBuildQty(Math.max(1, Number(e.target.value) || 1))}
                className="w-24 rounded border border-slate-300 px-2 py-1 text-sm dark:border-zinc-700 dark:bg-zinc-900"
              />
            </div>
          </div>

          <DataTable
            columns={[
              { header: "Internal PN", accessorKey: "internal_part_number" },
              { header: "MPN", accessorKey: "mpn" },
              { header: "Qty / Board", accessorKey: "quantity_per_board" },
              { header: "Required", accessorKey: "required" },
              { header: "Available", accessorKey: "available" },
              { header: "Shortage", accessorKey: "shortage" },
              {
                header: "Status",
                accessorKey: "status",
                cell: (r: AvailabilityItem) => (
                  <Badge tone={r.status === "SHORTAGE" ? "red" : "green"}>{r.status}</Badge>
                ),
              },
            ]}
            data={availability.items}
          />
        </div>
      )}
    </div>
  );
}
