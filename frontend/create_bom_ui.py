import os

os.makedirs('frontend/src/app/(app)/bom', exist_ok=True)
os.makedirs('frontend/src/app/(app)/bom/[id]', exist_ok=True)
os.makedirs('frontend/src/app/(app)/bom-revisions/[id]', exist_ok=True)
os.makedirs('frontend/src/app/(app)/bom-revisions/compare', exist_ok=True)
os.makedirs('frontend/src/app/(app)/bom/[id]/import', exist_ok=True)

# 1. bom/page.tsx
bom_list = """\"use client\";
import { useQuery } from "@tanstack/react-query";
import { Plus } from "lucide-react";
import Link from "next/link";
import { useState } from "react";
import { Button } from "@/components/ui/button";
import { DataTable } from "@/components/ui/data-table";
import { ErrorState, Spinner } from "@/components/ui/primitives";
import { api } from "@/lib/api";

export default function BomPage() {
  const [page, setPage] = useState(1);
  const { data, isLoading, error } = useQuery({
    queryKey: ["boms", page],
    queryFn: () => api.get(`/api/boms/?page=${page}`).then(r => r.json()),
  });

  if (isLoading) return <Spinner className="mt-10" />;
  if (error) return <ErrorState message="Failed to load BOMs." />;

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold text-slate-900 dark:text-white">BOM Manager</h1>
        <Button onClick={() => alert("Create modal pending")}><Plus className="mr-2 h-4 w-4" /> New BOM</Button>
      </div>
      <DataTable
        columns={[
          { header: "BOM Name", accessorKey: "name", cell: (r) => <Link href={`/bom/${r.id}`} className="font-medium text-emerald-600 hover:underline">{r.name}</Link> },
          { header: "Project", accessorKey: "project" },
          { header: "Status", accessorKey: "status" },
        ]}
        data={data.results}
      />
    </div>
  );
}
"""
with open('frontend/src/app/(app)/bom/page.tsx', 'w', encoding='utf-8') as f: f.write(bom_list)

# 2. bom/[id]/page.tsx
bom_detail = """\"use client\";
import { useQuery } from "@tanstack/react-query";
import { useParams, useRouter } from "next/navigation";
import Link from "next/link";
import { Button } from "@/components/ui/button";
import { DataTable } from "@/components/ui/data-table";
import { ErrorState, Spinner } from "@/components/ui/primitives";
import { api } from "@/lib/api";
import { BOM } from "@/lib/types";
import { FileUp, GitCompare } from "lucide-react";

export default function BomDetail() {
  const params = useParams();
  const bomId = params.id;
  
  const { data: bom, isLoading, error } = useQuery<BOM>({
    queryKey: ["boms", bomId],
    queryFn: () => api.get(`/api/boms/${bomId}/`).then(r => r.json()),
  });

  if (isLoading) return <Spinner className="mt-10" />;
  if (error || !bom) return <ErrorState message="Failed to load BOM." />;

  return (
    <div className="space-y-6">
      <div className="flex justify-between items-start">
        <div>
          <h1 className="text-3xl font-bold text-slate-900 dark:text-white">{bom.name}</h1>
          <p className="text-slate-500 mt-1">{bom.description || "Project ID: " + bom.project}</p>
        </div>
        <div className="flex gap-2">
          <Link href={`/bom/${bom.id}/import`}><Button variant="outline"><FileUp className="mr-2 h-4 w-4" /> Import KiCad CSV</Button></Link>
          <Link href={`/bom-revisions/compare?bom=${bom.id}`}><Button variant="outline"><GitCompare className="mr-2 h-4 w-4" /> Compare</Button></Link>
        </div>
      </div>

      <div className="border rounded-xl p-4 bg-white dark:bg-zinc-950 dark:border-zinc-800">
        <h2 className="text-lg font-semibold mb-4 text-slate-900 dark:text-white">Revision History</h2>
        <DataTable
          columns={[
            { header: "Revision", accessorKey: "revision_number", cell: (r) => <Link href={`/bom-revisions/${r.id}`} className="font-bold text-emerald-600 hover:underline">{r.revision_number}</Link> },
            { header: "Status", accessorKey: "status", cell: (r) => <span className={`px-2 py-1 rounded text-xs font-semibold ${r.status==='RELEASED' ? 'bg-blue-100 text-blue-800 dark:bg-blue-900 dark:text-blue-200' : 'bg-slate-100 text-slate-800 dark:bg-zinc-800 dark:text-zinc-200'}`}>{r.status}</span> },
            { header: "Date", accessorKey: "created_at", cell: (r) => new Date(r.created_at).toLocaleDateString() },
          ]}
          data={bom.revisions}
        />
      </div>
    </div>
  );
}
"""
with open('frontend/src/app/(app)/bom/[id]/page.tsx', 'w', encoding='utf-8') as f: f.write(bom_detail)

# 3. bom-revisions/[id]/page.tsx
rev_detail = """\"use client\";
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
    queryFn: () => api.get(`/api/bom-revisions/${revId}/`).then(r => r.json()),
  });

  const releaseMut = useMutation({
    mutationFn: () => api.post(`/api/bom-revisions/${revId}/release/`),
    onSuccess: () => {
      toast.success("BOM Released Successfully!");
      qc.invalidateQueries({ queryKey: ["bom_revision", revId] });
    },
    onError: () => toast.error("Failed to release BOM. Check permissions."),
  });

  if (isLoading) return <Spinner className="mt-10" />;
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
          { header: "Designators", accessorKey: "designators", cell: (r) => r.designators.join(", ") },
          { header: "Quantity", accessorKey: "quantity" },
          { header: "Unit Cost", accessorKey: "unit_cost_snapshot", cell: (r) => `$${Number(r.unit_cost_snapshot||0).toFixed(2)}` },
          { header: "Total", accessorKey: "total_cost_snapshot", cell: (r) => `$${Number(r.total_cost_snapshot||0).toFixed(2)}` },
        ]}
        data={rev.items}
      />
    </div>
  );
}
"""
with open('frontend/src/app/(app)/bom-revisions/[id]/page.tsx', 'w', encoding='utf-8') as f: f.write(rev_detail)

# 4. bom-revisions/compare/page.tsx
compare_detail = """\"use client\";
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

  const { data: bom } = useQuery({
    queryKey: ["boms", bomId],
    queryFn: () => api.get(`/api/boms/${bomId}/`).then(r => r.json()),
    enabled: !!bomId
  });

  const { data: diffs, isLoading, refetch } = useQuery({
    queryKey: ["bom_compare", revA, revB],
    queryFn: () => api.get(`/api/bom-revisions/compare/?rev_a=${revA}&rev_b=${revB}`).then(r => r.json()),
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
            { header: "Status", accessorKey: "status", cell: (r) => {
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
            { header: "Designators A", accessorKey: "designators_a", cell: (r) => r.designators_a.join(", ") },
            { header: "Designators B", accessorKey: "designators_b", cell: (r) => r.designators_b.join(", ") },
          ]}
          data={diffs.diff}
        />
      )}
    </div>
  );
}
"""
with open('frontend/src/app/(app)/bom-revisions/compare/page.tsx', 'w', encoding='utf-8') as f: f.write(compare_detail)
