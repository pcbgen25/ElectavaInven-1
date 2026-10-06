"use client";

import { useQuery } from "@tanstack/react-query";
import { Plus } from "lucide-react";
import Link from "next/link";
import { useState } from "react";

import { Button } from "@/components/ui/button";
import { DataTable } from "@/components/ui/data-table";
import { ErrorState, Spinner } from "@/components/ui/primitives";
import { api } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { Project } from "@/lib/types";

export default function ProjectsPage() {
  const { can } = useAuth();
  const [page, setPage] = useState(1);

  const { data, isLoading, error } = useQuery<any>({
    queryKey: ["projects", page],
    queryFn: () => api(`/api/projects/?page=${page}`),
  });

  if (isLoading) return <div className="mt-10 flex justify-center"><Spinner /></div>;
  if (error) return <ErrorState message="Failed to load projects." />;

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold text-slate-900 dark:text-white">Projects</h1>
        {can("project.create") && (
          <Button onClick={() => alert("Create modal pending")}>
            <Plus className="mr-2 h-4 w-4" /> New Project
          </Button>
        )}
      </div>

      <DataTable
        columns={[
          { header: "Code", accessorKey: "code" },
          { header: "Name", accessorKey: "name", cell: (r: any) => <Link href={`/projects/${r.id}`} className="font-medium text-emerald-600 hover:underline">{r.name}</Link> },
          { header: "Status", accessorKey: "status" },
          { header: "Customer", accessorKey: "customer" },
        ]}
        data={data.results}
      />
      <div className="flex justify-between mt-4">
        <Button disabled={!data.previous} onClick={() => setPage((p) => p - 1)}>Previous</Button>
        <Button disabled={!data.next} onClick={() => setPage((p) => p + 1)}>Next</Button>
      </div>
    </div>
  );
}
