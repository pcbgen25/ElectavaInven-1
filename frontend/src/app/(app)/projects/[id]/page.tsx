"use client";

import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { useParams } from "next/navigation";
import { Trash2, Edit, Plus } from "lucide-react";
import Link from "next/link";
import { useState } from "react";

import { DataTable, type Column } from "@/components/data-table/data-table";
import { Button } from "@/components/ui/button";
import { Field, Input, Select, Textarea } from "@/components/ui/form";
import { PageHeader, Modal, Badge, ErrorState, Spinner, DescriptionList } from "@/components/ui/primitives";
import { useToast } from "@/components/ui/toast";
import { api, ApiError } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { BOM, Project, ProjectMember, ProjectStatus } from "@/lib/types";

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

export default function ProjectDetail() {
  const { id } = useParams();
  const { can } = useAuth();
  const qc = useQueryClient();
  const toast = useToast();
  
  const [editModal, setEditModal] = useState(false);
  const [addMemberModal, setAddMemberModal] = useState(false);

  const { data: project, isLoading, error } = useQuery<Project>({
    queryKey: ["projects", id],
    queryFn: () => api(`projects/${id}`),
  });

  const { data: boms, isLoading: bomsLoading } = useQuery<{ count: number; results: BOM[] }>({
    queryKey: ["project_boms", id],
    queryFn: () => api(`boms?project=${id}`),
  });

  const removeMember = useMutation({
    mutationFn: (memberId: number) => api(`projects/${id}/members/${memberId}`, { method: "DELETE" }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["projects", id] });
      toast("Member removed");
    },
    onError: () => toast("Failed to remove member", "error")
  });

  if (isLoading) return <div className="mt-10 flex justify-center"><Spinner /></div>;
  if (error || !project) return <div className="mt-4"><ErrorState message="Failed to load project." /></div>;

  const memberColumns: Column<ProjectMember>[] = [
    { key: "name", header: "Name", render: (m) => <span className="font-medium">{m.user_details.full_name || m.user_details.email}</span> },
    { key: "notes", header: "Notes", render: (m) => <span className="text-slate-500">{m.notes || "—"}</span> },
    { key: "actions", header: "", render: (m) => can("project.manage_members") && (
      <div className="flex justify-end">
        <Button variant="ghost" size="sm" onClick={() => removeMember.mutate(m.id)} loading={removeMember.isPending} aria-label="Remove member">
          <Trash2 className="h-4 w-4 text-red-500" />
        </Button>
      </div>
    ) },
  ];

  const bomColumns: Column<import("@/lib/types").BOM>[] = [
    { key: "name", header: "BOM Name", render: (b) => <Link href={`/bom/${b.id}`} className="font-medium text-blue-700 hover:underline">{b.name}</Link> },
    { key: "status", header: "Status", render: (b) => <span className="text-slate-600">{b.status}</span> },
  ];

  return (
    <>
      <PageHeader
        title={<div className="flex items-center gap-3">
          <span>{project.code}</span>
          <Badge tone={STATUS_TONES[project.status]}>{STATUS_LABELS[project.status]}</Badge>
        </div>}
        subtitle={project.name}
        actions={can("project.edit") && <Button variant="secondary" onClick={() => setEditModal(true)}><Edit className="h-4 w-4 mr-2" /> Edit Project</Button>}
      />

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <div className="lg:col-span-2 space-y-6">
          <div className="rounded-lg border border-slate-200 bg-white p-4">
            <h2 className="text-base font-semibold text-slate-900 mb-4">Project Details</h2>
            <DescriptionList items={[
              { label: "Customer", value: project.customer },
              { label: "Target Date", value: project.target_date },
              { label: "Start Date", value: project.start_date },
              { label: "Description", value: project.description },
            ]} />
          </div>

          <div className="space-y-3">
            <div className="flex items-center justify-between">
              <h2 className="text-base font-semibold text-slate-900">BOMs</h2>
              <Link href={`/bom?project=${project.id}`}><Button variant="secondary" size="sm">View All</Button></Link>
            </div>
            {bomsLoading ? <Spinner /> : (
              <DataTable
                id="project-boms"
                columns={bomColumns}
                rows={boms?.results || []}
                count={boms?.count ?? 0}
                page={1}
                pageSize={100}
                ordering=""
                loading={bomsLoading}
                rowKey={(b) => b.id}
                empty={<p className="p-4 text-sm text-slate-500">No BOMs for this project yet.</p>}
                onOrdering={() => {}}
                onPage={() => {}}
              />
            )}
          </div>
        </div>

        <div className="space-y-3">
          <div className="flex items-center justify-between">
            <h2 className="text-base font-semibold text-slate-900">Members</h2>
            {can("project.manage_members") && <Button variant="secondary" size="sm" onClick={() => setAddMemberModal(true)}><Plus className="h-4 w-4 mr-1" /> Add</Button>}
          </div>
          <DataTable
            id="project-members"
            columns={memberColumns}
            rows={project.members}
            count={project.members.length}
            page={1}
            pageSize={100}
            ordering=""
            loading={false}
            rowKey={(m) => m.id}
            empty={<p className="p-4 text-sm text-slate-500">No members added yet.</p>}
            onOrdering={() => {}}
            onPage={() => {}}
          />
        </div>
      </div>

      <EditProjectModal open={editModal} onClose={() => setEditModal(false)} project={project} />
      <AddMemberModal open={addMemberModal} onClose={() => setAddMemberModal(false)} projectId={project.id} />
    </>
  );
}

function EditProjectModal({ open, onClose, project }: { open: boolean; onClose: () => void; project: Project }) {
  const qc = useQueryClient();
  const toast = useToast();
  const [errors, setErrors] = useState<Record<string, string[]>>({});
  
  const { mutate, isPending } = useMutation({
    mutationFn: (data: unknown) => api(`projects/${project.id}`, { method: "PATCH", body: data }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["projects"] });
      toast("Project updated successfully");
      onClose();
    },
    onError: (err) => {
      if (err instanceof ApiError) setErrors(err.fieldErrors);
      else toast("Failed to update project", "error");
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
      start_date: fd.get("start_date") || null,
      target_date: fd.get("target_date") || null,
      status: fd.get("status")
    });
  };

  return (
    <Modal open={open} onClose={onClose} title="Edit Project" footer={
      <>
        <Button variant="secondary" onClick={onClose} disabled={isPending}>Cancel</Button>
        <Button type="submit" form="edit-project-form" loading={isPending}>Save Changes</Button>
      </>
    }>
      <form id="edit-project-form" onSubmit={onSubmit} className="space-y-4">
        {errors.non_field_errors && <div className="text-sm text-red-600">{errors.non_field_errors.join(", ")}</div>}
        <Field label="Status" htmlFor="status" required error={errors.status}>
          <Select id="status" name="status" defaultValue={project.status} required invalid={!!errors.status}>
            {Object.entries(STATUS_LABELS).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
          </Select>
        </Field>
        <Field label="Project Code" htmlFor="code" required error={errors.code}>
          <Input id="code" name="code" defaultValue={project.code} required invalid={!!errors.code} />
        </Field>
        <Field label="Name" htmlFor="name" required error={errors.name}>
          <Input id="name" name="name" defaultValue={project.name} required invalid={!!errors.name} />
        </Field>
        <Field label="Customer" htmlFor="customer" error={errors.customer}>
          <Input id="customer" name="customer" defaultValue={project.customer || ""} invalid={!!errors.customer} />
        </Field>
        <div className="grid grid-cols-2 gap-4">
          <Field label="Start Date" htmlFor="start_date" error={errors.start_date}>
            <Input id="start_date" name="start_date" type="date" defaultValue={project.start_date || ""} invalid={!!errors.start_date} />
          </Field>
          <Field label="Target Date" htmlFor="target_date" error={errors.target_date}>
            <Input id="target_date" name="target_date" type="date" defaultValue={project.target_date || ""} invalid={!!errors.target_date} />
          </Field>
        </div>
        <Field label="Description" htmlFor="description" error={errors.description}>
          <Textarea id="description" name="description" defaultValue={project.description || ""} invalid={!!errors.description} />
        </Field>
      </form>
    </Modal>
  );
}

function AddMemberModal({ open, onClose, projectId }: { open: boolean; onClose: () => void; projectId: number | string }) {
  const qc = useQueryClient();
  const toast = useToast();
  const [errors, setErrors] = useState<Record<string, string[]>>({});
  
  const { data: candidates, isLoading } = useQuery<import("@/lib/types").User[]>({
    queryKey: ["project_candidates", projectId],
    queryFn: () => api(`projects/${projectId}/member-candidates`),
    enabled: open
  });

  const { mutate, isPending } = useMutation({
    mutationFn: (data: unknown) => api(`projects/${projectId}/members`, { method: "POST", body: data }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["projects", String(projectId)] });
      qc.invalidateQueries({ queryKey: ["project_candidates", projectId] });
      toast("Member added");
      onClose();
    },
    onError: (err) => {
      if (err instanceof ApiError) setErrors(err.fieldErrors);
      else toast("Failed to add member", "error");
    }
  });

  const onSubmit = (e: React.FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    setErrors({});
    const fd = new FormData(e.currentTarget);
    mutate({
      user: fd.get("user"),
      notes: fd.get("notes")
    });
  };

  return (
    <Modal open={open} onClose={onClose} title="Add Member" footer={
      <>
        <Button variant="secondary" onClick={onClose} disabled={isPending}>Cancel</Button>
        <Button type="submit" form="add-member-form" loading={isPending}>Add</Button>
      </>
    }>
      <form id="add-member-form" onSubmit={onSubmit} className="space-y-4">
        {errors.non_field_errors && <div className="text-sm text-red-600">{errors.non_field_errors.join(", ")}</div>}
        <Field label="User" htmlFor="user" required error={errors.user}>
          <Select id="user" name="user" required invalid={!!errors.user} disabled={isLoading}>
            <option value="">Select a user...</option>
            {candidates?.map((c) => <option key={c.id} value={c.id}>{c.full_name || c.email}</option>)}
          </Select>
        </Field>
        <Field label="Notes" htmlFor="notes" error={errors.notes}>
          <Input id="notes" name="notes" placeholder="Role in project..." invalid={!!errors.notes} />
        </Field>
      </form>
    </Modal>
  );
}
