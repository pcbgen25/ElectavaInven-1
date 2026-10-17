"use client";

import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { Plus } from "lucide-react";
import { useState } from "react";

import { DataTable, type Column } from "@/components/data-table/data-table";
import { Button } from "@/components/ui/button";
import { Field, Input, Textarea } from "@/components/ui/form";
import { PageHeader, Modal, Badge } from "@/components/ui/primitives";
import { useToast } from "@/components/ui/toast";
import { api, type Paginated, ApiError } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { Project, ProjectStatus } from "@/lib/types";
import { useListState } from "@/lib/use-list-state";
import { formatDateTime } from "@/lib/utils";

const STATUS_LABELS: Record<ProjectStatus, string> = {
  DRAFT: "Draft",
  ACTIVE: "Active",
  ON_HOLD: "On Hold",
  COMPLETED: "Completed",
  CANCELLED: "Cancelled"
};

const STATUS_TONES: Record<ProjectStatus, "slate" | "blue" | "amber" | "green" | "red"> = {
  DRAFT: "slate",
  ACTIVE: "blue",
  ON_HOLD: "amber",
  COMPLETED: "green",
  CANCELLED: "red"
};

const COLUMNS: Column<Project>[] = [
  { key: "code", header: "Code", sortKey: "code", render: (p) => <span className="font-medium text-slate-900">{p.code}</span> },
  { key: "name", header: "Name", sortKey: "name", render: (p) => p.name },
  { key: "customer", header: "Customer", sortKey: "customer", render: (p) => p.customer || "—" },
  { key: "status", header: "Status", sortKey: "status", render: (p) => <Badge tone={STATUS_TONES[p.status]}>{STATUS_LABELS[p.status]}</Badge> },
  { key: "target_date", header: "Target Date", sortKey: "target_date", render: (p) => p.target_date || "—" },
  { key: "updated_at", header: "Updated", sortKey: "updated_at", render: (p) => <span className="text-slate-500 whitespace-nowrap">{formatDateTime(p.updated_at)}</span>, hiddenByDefault: true },
];

export default function ProjectsPage() {
  const { can } = useAuth();
  const list = useListState({ ordering: "-updated_at" });
  const [modalOpen, setModalOpen] = useState(false);
  
  const { data, isFetching, error, refetch } = useQuery({
    queryKey: ["projects", list.query],
    queryFn: () => api<Paginated<Project>>("projects", { query: list.query }),
  });

  return (
    <>
      <PageHeader
        title="Projects"
        subtitle="Manage hardware projects and their active BOMs"
        actions={can("project.create") && <Button onClick={() => setModalOpen(true)}><Plus className="h-4 w-4 mr-2" /> New Project</Button>}
      />
      <DataTable
        id="projects"
        columns={COLUMNS}
        rows={data?.results}
        count={data?.count ?? 0}
        page={list.page}
        pageSize={list.pageSize}
        ordering={list.ordering}
        loading={isFetching}
        error={error ? (error as Error).message : null}
        onRetry={() => refetch()}
        search={list.search}
        onSearch={(v) => list.update({ search: v })}
        searchPlaceholder="Search projects by code, name, customer..."
        onOrdering={(o) => list.update({ ordering: o })}
        onPage={(p) => list.update({ page: p }, false)}
        onPageSize={(s) => list.update({ page_size: s })}
        rowKey={(p) => p.id}
        rowHref={(p) => `/projects/${p.id}`}
      />
      <CreateProjectModal open={modalOpen} onClose={() => setModalOpen(false)} />
    </>
  );
}

function CreateProjectModal({ open, onClose }: { open: boolean; onClose: () => void }) {
  const qc = useQueryClient();
  const toast = useToast();
  const [errors, setErrors] = useState<Record<string, string[]>>({});
  
  const { mutate, isPending } = useMutation({
    mutationFn: (data: unknown) => api("projects", { method: "POST", body: data }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["projects"] });
      toast("Project created successfully");
      onClose();
    },
    onError: (err) => {
      if (err instanceof ApiError) setErrors(err.fieldErrors);
      else toast("Failed to create project", "error");
    }
  });

  const onSubmit = (e: React.FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    setErrors({});
    const fd = new FormData(e.currentTarget);
    mutate({
      code: fd.get("code"),
      name: fd.get("name"),
      description: fd.get("description"),
      customer: fd.get("customer"),
      target_date: fd.get("target_date") || null,
      status: "DRAFT"
    });
  };

  return (
    <Modal open={open} onClose={onClose} title="New Project" footer={
      <>
        <Button variant="secondary" onClick={onClose} disabled={isPending}>Cancel</Button>
        <Button type="submit" form="create-project-form" loading={isPending}>Create Project</Button>
      </>
    }>
      <form id="create-project-form" onSubmit={onSubmit} className="space-y-4">
        {errors.non_field_errors && <div className="text-sm text-red-600">{errors.non_field_errors.join(", ")}</div>}
        <Field label="Project Code" htmlFor="code" required error={errors.code}>
          <Input id="code" name="code" required placeholder="PRJ-001" invalid={!!errors.code} />
        </Field>
        <Field label="Name" htmlFor="name" required error={errors.name}>
          <Input id="name" name="name" required placeholder="Project Apollo" invalid={!!errors.name} />
        </Field>
        <Field label="Customer" htmlFor="customer" error={errors.customer}>
          <Input id="customer" name="customer" placeholder="Acme Corp" invalid={!!errors.customer} />
        </Field>
        <Field label="Target Date" htmlFor="target_date" error={errors.target_date}>
          <Input id="target_date" name="target_date" type="date" invalid={!!errors.target_date} />
        </Field>
        <Field label="Description" htmlFor="description" error={errors.description}>
          <Textarea id="description" name="description" placeholder="Project details..." invalid={!!errors.description} />
        </Field>
      </form>
    </Modal>
  );
}