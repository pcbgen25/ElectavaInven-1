"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Plus } from "lucide-react";
import Link from "next/link";
import { useState } from "react";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import { DataTable } from "@/components/ui/data-table";
import { Field, Input, Select, Textarea } from "@/components/ui/form";
import { ErrorState, Modal, Spinner } from "@/components/ui/primitives";
import { ApiError, type Paginated, api } from "@/lib/api";
import type { BOM, Project } from "@/lib/types";

export default function BomPage() {
  const [page, setPage] = useState(1);
  const [createOpen, setCreateOpen] = useState(false);
  const queryClient = useQueryClient();
  const [form, setForm] = useState({ name: "", description: "", project: "" });
  const [errors, setErrors] = useState<Record<string, string[]>>({});

  const { data, isLoading, error } = useQuery<Paginated<BOM>>({
    queryKey: ["boms", page],
    queryFn: () => api<Paginated<BOM>>(`boms/?page=${page}`),
  });

  const { data: projects } = useQuery<Paginated<Project>>({
    queryKey: ["projects", "options"],
    queryFn: () => api<Paginated<Project>>("projects/?page_size=200"),
    enabled: createOpen,
  });

  const createMut = useMutation({
    mutationFn: async (payload: typeof form) => {
      return api<BOM>("boms/", {
        method: "POST",
        body: {
          name: payload.name,
          description: payload.description,
          project: Number(payload.project),
        },
      });
    },
    onSuccess: () => {
      toast.success("BOM created successfully");
      setCreateOpen(false);
      setForm({ name: "", description: "", project: "" });
      setErrors({});
      queryClient.invalidateQueries({ queryKey: ["boms"] });
    },
    onError: (err: unknown) => {
      if (err instanceof ApiError) {
        setErrors(err.fieldErrors);
        toast.error(err.message);
      } else {
        toast.error("Failed to create BOM");
      }
    },
  });

  if (isLoading)
    return (
      <div className="mt-10 flex justify-center">
        <Spinner />
      </div>
    );
  if (error || !data) return <ErrorState message="Failed to load BOMs." />;

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold text-slate-900 dark:text-white">BOM Manager</h1>
        <Button onClick={() => setCreateOpen(true)}>
          <Plus className="mr-2 h-4 w-4" /> New BOM
        </Button>
      </div>
      <DataTable
        columns={[
          {
            header: "BOM Name",
            accessorKey: "name",
            cell: (r: BOM) => (
              <Link href={`/bom/${r.id}`} className="font-medium text-emerald-600 hover:underline">
                {r.name}
              </Link>
            ),
          },
          { header: "Project ID", accessorKey: "project" },
          { header: "Status", accessorKey: "status" },
        ]}
        data={data.results}
      />

      <div className="flex items-center gap-2">
        <Button variant="secondary" size="sm" disabled={!data.previous} onClick={() => setPage((p) => Math.max(1, p - 1))}>
          Previous
        </Button>
        <span className="text-sm text-slate-500">Page {page}</span>
        <Button variant="secondary" size="sm" disabled={!data.next} onClick={() => setPage((p) => p + 1)}>
          Next
        </Button>
      </div>

      <Modal
        open={createOpen}
        onClose={() => setCreateOpen(false)}
        title="Create BOM"
        footer={
          <>
            <Button variant="ghost" onClick={() => setCreateOpen(false)}>
              Cancel
            </Button>
            <Button onClick={() => createMut.mutate(form)} loading={createMut.isPending}>
              Create BOM
            </Button>
          </>
        }
      >
        <div className="space-y-4">
          <Field label="BOM Name" htmlFor="name" required error={errors.name}>
            <Input id="name" value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} />
          </Field>
          <Field label="Project" htmlFor="project" required error={errors.project}>
            <Select id="project" value={form.project} onChange={(e) => setForm({ ...form, project: e.target.value })}>
              <option value="">Select project...</option>
              {projects?.results?.map((p) => (
                <option key={p.id} value={p.id}>
                  {p.code} — {p.name}
                </option>
              ))}
            </Select>
          </Field>
          <Field label="Description" htmlFor="description" error={errors.description}>
            <Textarea id="description" value={form.description} onChange={(e) => setForm({ ...form, description: e.target.value })} />
          </Field>
        </div>
      </Modal>
    </div>
  );
}
