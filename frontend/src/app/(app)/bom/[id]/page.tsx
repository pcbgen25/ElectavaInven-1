"use client";
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
    queryFn: () => api(`/api/boms/${bomId}/`),
  });

  if (isLoading) return <div className="mt-10 flex justify-center"><Spinner /></div>;
  if (error || !bom) return <ErrorState message="Failed to load BOM." />;

  return (
    <div className="space-y-6">
      <div className="flex justify-between items-start">
        <div>
          <h1 className="text-3xl font-bold text-slate-900 dark:text-white">{bom.name}</h1>
          <p className="text-slate-500 mt-1">{bom.description || "Project ID: " + bom.project}</p>
        </div>
        <div className="flex gap-2">
          <Link href={`/bom/${bom.id}/import`}><Button variant="secondary"><FileUp className="mr-2 h-4 w-4" /> Import KiCad CSV</Button></Link>
          <Link href={`/bom-revisions/compare?bom=${bom.id}`}><Button variant="secondary"><GitCompare className="mr-2 h-4 w-4" /> Compare</Button></Link>
        </div>
      </div>

      <div className="border rounded-xl p-4 bg-white dark:bg-zinc-950 dark:border-zinc-800">
        <h2 className="text-lg font-semibold mb-4 text-slate-900 dark:text-white">Revision History</h2>
        <DataTable
          columns={[
            { header: "Revision", accessorKey: "revision_number", cell: (r: any) => <Link href={`/bom-revisions/${r.id}`} className="font-bold text-emerald-600 hover:underline">{r.revision_number}</Link> },
            { header: "Status", accessorKey: "status", cell: (r: any) => <span className={`px-2 py-1 rounded text-xs font-semibold ${r.status==='RELEASED' ? 'bg-blue-100 text-blue-800 dark:bg-blue-900 dark:text-blue-200' : 'bg-slate-100 text-slate-800 dark:bg-zinc-800 dark:text-zinc-200'}`}>{r.status}</span> },
            { header: "Date", accessorKey: "created_at", cell: (r: any) => new Date(r.created_at).toLocaleDateString() },
          ]}
          data={bom.revisions}
        />
      </div>
    </div>
  );
}
