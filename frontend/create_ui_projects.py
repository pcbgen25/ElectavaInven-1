import os

os.makedirs('frontend/src/app/(app)/projects', exist_ok=True)

projects_list_code = """\"use client\";

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

  const { data, isLoading, error } = useQuery({
    queryKey: ["projects", page],
    queryFn: () => api.get(`/api/projects/?page=${page}`).then(r => r.json()),
  });

  if (isLoading) return <Spinner className="mt-10" />;
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
          { header: "Name", accessorKey: "name", cell: (r) => <Link href={`/projects/${r.id}`} className="font-medium text-emerald-600 hover:underline">{r.name}</Link> },
          { header: "Status", accessorKey: "status" },
          { header: "Customer", accessorKey: "customer" },
        ]}
        data={data.results}
      />
      <div className="flex justify-between mt-4">
        <Button disabled={!data.previous} onClick={() => setPage(p => p - 1)}>Previous</Button>
        <Button disabled={!data.next} onClick={() => setPage(p => p + 1)}>Next</Button>
      </div>
    </div>
  );
}
"""

with open('frontend/src/app/(app)/projects/page.tsx', 'w', encoding='utf-8') as f:
    f.write(projects_list_code)

os.makedirs('frontend/src/app/(app)/projects/[id]', exist_ok=True)
project_detail_code = """\"use client\";

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
    queryFn: () => api.get(`/api/projects/${projectId}/`).then(r => r.json()),
  });

  const { data: boms, isLoading: bomsLoading } = useQuery({
    queryKey: ["project_boms", projectId],
    queryFn: () => api.get(`/api/boms/?project=${projectId}`).then(r => r.json()),
  });

  if (isLoading) return <Spinner className="mt-10" />;
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
                { header: "BOM Name", accessorKey: "name", cell: (r) => <Link href={`/bom/${r.id}`} className="text-emerald-600 hover:underline">{r.name}</Link> },
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
"""

with open('frontend/src/app/(app)/projects/[id]/page.tsx', 'w', encoding='utf-8') as f:
    f.write(project_detail_code)
