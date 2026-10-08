"use client";

import { useQuery } from "@tanstack/react-query";
import { useParams } from "next/navigation";
import { Button } from "@/components/ui/button";
import { DataTable } from "@/components/ui/data-table";
import { ErrorState, Spinner } from "@/components/ui/primitives";
import { api } from "@/lib/api";
import { Project } from "@/lib/types";
import Link from "next/link";

export default function ProjectDetail() {
  const params = useParams();
  const projectId = params.id;

  const { data: project, isLoading, error } = useQuery<Project>({
    queryKey: ["projects", projectId],
    queryFn: () => api(`/projects/${projectId}/`),
  });

  const { data: boms, isLoading: bomsLoading } = useQuery<any>({
    queryKey: ["project_boms", projectId],
    queryFn: () => api(`/boms/?project=${projectId}`),
  });

  if (isLoading) return <div className="mt-10 flex justify-center"><Spinner /></div>;
  if (error || !project) return <ErrorState message="Failed to load project." />;

  return (
    <div className="space-y-6">
      <div className="flex justify-between items-start">
        <div>
          <h1 className="text-3xl font-bold text-slate-900 dark:text-white">{project.code} - {project.name}</h1>
          <p className="text-slate-500 mt-1">{project.description || "No description provided."}</p>
        </div>
        <div className="flex gap-2">
           <span className="px-3 py-1 rounded-full bg-slate-100 text-slate-800 text-sm font-medium dark:bg-zinc-800 dark:text-zinc-200">{project.status}</span>
        </div>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        <div className="border rounded-xl p-4 bg-white dark:bg-zinc-950 dark:border-zinc-800">
          <h2 className="text-lg font-semibold mb-4 text-slate-900 dark:text-white">Members</h2>
          <DataTable
            columns={[
              { header: "Name", accessorKey: "user_details.full_name" },
              { header: "Notes", accessorKey: "notes" },
            ]}
            data={project.members}
          />
        </div>

        <div className="border rounded-xl p-4 bg-white dark:bg-zinc-950 dark:border-zinc-800">
          <div className="flex justify-between items-center mb-4">
            <h2 className="text-lg font-semibold text-slate-900 dark:text-white">BOMs</h2>
            <Link href={`/bom?project=${project.id}`}><Button size="sm">View All</Button></Link>
          </div>
          {bomsLoading ? <Spinner /> : (
            <DataTable
              columns={[
                { header: "BOM Name", accessorKey: "name", cell: (r: any) => <Link href={`/bom/${r.id}`} className="text-emerald-600 hover:underline">{r.name}</Link> },
                { header: "Status", accessorKey: "status" },
              ]}
              data={boms?.results || []}
            />
          )}
        </div>
      </div>
    </div>
  );
}
