"use client";
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
  const { data, isLoading, error } = useQuery<any>({
    queryKey: ["boms", page],
    queryFn: () => api(`/api/boms/?page=${page}`),
  });

  if (isLoading) return <div className="mt-10 flex justify-center"><Spinner /></div>;
  if (error) return <ErrorState message="Failed to load BOMs." />;

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold text-slate-900 dark:text-white">BOM Manager</h1>
        <Button onClick={() => alert("Create modal pending")}><Plus className="mr-2 h-4 w-4" /> New BOM</Button>
      </div>
      <DataTable
        columns={[
          { header: "BOM Name", accessorKey: "name", cell: (r: any) => <Link href={`/bom/${r.id}`} className="font-medium text-emerald-600 hover:underline">{r.name}</Link> },
          { header: "Project", accessorKey: "project" },
          { header: "Status", accessorKey: "status" },
        ]}
        data={data.results}
      />
    </div>
  );
}
