"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ClipboardList, Plus, Search, Trash2 } from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import { Badge, Card, EmptyState, ErrorState, Modal, PageHeader, Spinner } from "@/components/ui/primitives";
import { api, ApiError, type Paginated } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import type {
  BOMRevision,
  ComponentListItem,
  Project,
  PurchasePriority,
  PurchaseRequest,
  PurchaseRequestStatus,
} from "@/lib/types";
import { formatDateTime } from "@/lib/utils";

const STATUS_TONE: Record<PurchaseRequestStatus, "slate" | "amber" | "green" | "red" | "blue"> = {
  DRAFT: "slate",
  SUBMITTED: "amber",
  APPROVED: "green",
  REJECTED: "red",
  ORDERED: "blue",
  CANCELLED: "red",
};

export default function PurchaseRequestsPage() {
  const { can } = useAuth();
  const router = useRouter();
  const qc = useQueryClient();

  const [search, setSearch] = useState("");
  const [statusFilter, setStatusFilter] = useState("");
  const [openCreate, setOpenCreate] = useState(false);
  const [openShortage, setOpenShortage] = useState(false);

  const [form, setForm] = useState({
    title: "",
    project: "",
    priority: "NORMAL" as PurchasePriority,
    needed_by: "",
    notes: "",
    lines: [{ component: "", quantity: "10", estimated_unit_price: "", notes: "" }],
  });

  const [shortageForm, setShortageForm] = useState({
    bom_revision: "",
    build_quantity: "10",
    priority: "HIGH" as PurchasePriority,
    apply_moq: true,
    notes: "",
  });

  const { data, isLoading, error } = useQuery<Paginated<PurchaseRequest>>({
    queryKey: ["purchasing-requests", search, statusFilter],
    queryFn: () =>
      api<Paginated<PurchaseRequest>>("purchasing/requests", {
        query: {
          search: search || undefined,
          status: statusFilter || undefined,
          page_size: 100,
        },
      }),
  });

  const { data: projectsData } = useQuery<Paginated<Project>>({
    queryKey: ["projects", "dropdown"],
    queryFn: () => api<Paginated<Project>>("projects", { query: { page_size: 100 } }),
    enabled: openCreate,
  });

  const { data: componentsData } = useQuery<Paginated<ComponentListItem>>({
    queryKey: ["components", "dropdown"],
    queryFn: () => api<Paginated<ComponentListItem>>("components", { query: { page_size: 100 } }),
    enabled: openCreate,
  });

  const { data: revisionsData } = useQuery<Paginated<BOMRevision>>({
    queryKey: ["bom-revisions", "dropdown"],
    queryFn: () => api<Paginated<BOMRevision>>("bom-revisions", { query: { page_size: 100 } }),
    enabled: openShortage,
  });

  const createMut = useMutation({
    mutationFn: () =>
      api<PurchaseRequest>("purchasing/requests", {
        method: "POST",
        body: {
          title: form.title,
          project: form.project ? Number(form.project) : null,
          priority: form.priority,
          needed_by: form.needed_by || null,
          notes: form.notes,
          items: form.lines
            .filter((l) => l.component && Number(l.quantity) > 0)
            .map((l) => ({
              component: Number(l.component),
              quantity: l.quantity,
              estimated_unit_price: l.estimated_unit_price ? l.estimated_unit_price : null,
              notes: l.notes,
            })),
        },
      }),
    onSuccess: (created) => {
      toast.success(`Purchase Request ${created.request_number} created`);
      setOpenCreate(false);
      qc.invalidateQueries({ queryKey: ["purchasing-requests"] });
      router.push(`/purchasing/requests/${created.id}`);
    },
    onError: (e) => toast.error(e instanceof ApiError ? e.message : "Failed to create purchase request"),
  });

  const shortageMut = useMutation({
    mutationFn: () =>
      api<PurchaseRequest>("purchasing/requests/from-bom-shortage", {
        method: "POST",
        body: {
          bom_revision: Number(shortageForm.bom_revision),
          build_quantity: shortageForm.build_quantity,
          priority: shortageForm.priority,
          apply_moq: shortageForm.apply_moq,
          notes: shortageForm.notes,
        },
      }),
    onSuccess: (created) => {
      toast.success(`Generated ${created.request_number} from BOM shortage`);
      setOpenShortage(false);
      qc.invalidateQueries({ queryKey: ["purchasing-requests"] });
      router.push(`/purchasing/requests/${created.id}`);
    },
    onError: (e) => toast.error(e instanceof ApiError ? e.message : "No shortage or failed to generate PR"),
  });

  const requests = data?.results ?? [];

  return (
    <div className="space-y-6">
      <PageHeader
        title="Purchase Requests"
        subtitle="Engineering & inventory requisitions with separation-of-duties approval."
        actions={
          can("purchase.create") && (
            <div className="flex gap-2">
              <Button variant="secondary" onClick={() => setOpenShortage(true)}>
                <ClipboardList className="h-4 w-4" /> From BOM Shortage
              </Button>
              <Button onClick={() => setOpenCreate(true)}>
                <Plus className="h-4 w-4" /> New Purchase Request
              </Button>
            </div>
          )
        }
      />

      <Card>
        <div className="flex flex-wrap items-center gap-3">
          <div className="relative min-w-[240px] flex-1">
            <Search className="pointer-events-none absolute left-3 top-2.5 h-4 w-4 text-slate-400" />
            <input
              type="text"
              placeholder="Search by PR #, title, project..."
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              className="w-full rounded-md border border-slate-300 py-1.5 pl-9 pr-3 text-sm"
            />
          </div>
          <select
            value={statusFilter}
            onChange={(e) => setStatusFilter(e.target.value)}
            className="rounded-md border border-slate-300 px-3 py-1.5 text-sm"
          >
            <option value="">All Statuses</option>
            <option value="DRAFT">Draft</option>
            <option value="SUBMITTED">Submitted</option>
            <option value="APPROVED">Approved</option>
            <option value="ORDERED">Ordered</option>
            <option value="REJECTED">Rejected</option>
            <option value="CANCELLED">Cancelled</option>
          </select>
        </div>
      </Card>

      {isLoading ? (
        <div className="flex justify-center py-12">
          <Spinner />
        </div>
      ) : error ? (
        <ErrorState message="Failed to load purchase requests." />
      ) : requests.length === 0 ? (
        <EmptyState
          title="No purchase requests"
          description="Create a purchase request manually or auto-generate one from a BOM revision stock shortage."
          action={
            can("purchase.create") && (
              <Button onClick={() => setOpenCreate(true)}>
                <Plus className="h-4 w-4" /> New Purchase Request
              </Button>
            )
          }
        />
      ) : (
        <div className="overflow-x-auto rounded-lg border border-slate-200 bg-white shadow-sm">
          <table className="w-full text-left text-sm">
            <thead className="border-b border-slate-200 bg-slate-50 text-xs font-semibold uppercase text-slate-600">
              <tr>
                <th className="px-4 py-3">PR #</th>
                <th className="px-4 py-3">Title</th>
                <th className="px-4 py-3">Project / BOM</th>
                <th className="px-4 py-3">Items</th>
                <th className="px-4 py-3">Est. Total</th>
                <th className="px-4 py-3">Priority</th>
                <th className="px-4 py-3">Status</th>
                <th className="px-4 py-3">Created</th>
                <th className="px-4 py-3 text-right">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {requests.map((pr) => (
                <tr key={pr.id} className="hover:bg-slate-50">
                  <td className="px-4 py-3 font-mono text-xs font-semibold text-blue-700">
                    <Link href={`/purchasing/requests/${pr.id}`} className="hover:underline">
                      {pr.request_number}
                    </Link>
                  </td>
                  <td className="px-4 py-3 font-medium text-slate-900">
                    <Link href={`/purchasing/requests/${pr.id}`} className="hover:text-blue-700 hover:underline">
                      {pr.title}
                    </Link>
                  </td>
                  <td className="px-4 py-3 text-xs text-slate-600">
                    {pr.project_code ? `${pr.project_code} — ${pr.project_name}` : "General"}
                    {pr.bom_revision_label && <div className="text-slate-400">{pr.bom_revision_label}</div>}
                  </td>
                  <td className="px-4 py-3 font-mono text-xs">{pr.item_count}</td>
                  <td className="px-4 py-3 font-mono text-xs font-semibold">
                    ${Number(pr.estimated_total).toFixed(2)}
                  </td>
                  <td className="px-4 py-3">
                    <Badge tone={pr.priority === "URGENT" || pr.priority === "HIGH" ? "red" : "slate"}>
                      {pr.priority}
                    </Badge>
                  </td>
                  <td className="px-4 py-3">
                    <Badge tone={STATUS_TONE[pr.status]}>{pr.status}</Badge>
                  </td>
                  <td className="px-4 py-3 text-xs text-slate-500">{formatDateTime(pr.created_at)}</td>
                  <td className="px-4 py-3 text-right">
                    <Link
                      href={`/purchasing/requests/${pr.id}`}
                      className="text-xs font-semibold text-blue-700 hover:underline"
                    >
                      Open
                    </Link>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {/* Create Purchase Request Modal */}
      <Modal
        open={openCreate}
        title="New Purchase Request"
        onClose={() => setOpenCreate(false)}
        footer={
          <>
            <Button variant="secondary" onClick={() => setOpenCreate(false)}>
              Cancel
            </Button>
            <Button
              loading={createMut.isPending}
              disabled={!form.title.trim() || form.lines.every((l) => !l.component)}
              onClick={() => createMut.mutate()}
            >
              Create Request
            </Button>
          </>
        }
      >
        <div className="space-y-4">
          <div className="grid gap-3 sm:grid-cols-2">
            <div className="sm:col-span-2">
              <label className="mb-1 block text-xs font-medium text-slate-700">Request Title *</label>
              <input
                type="text"
                value={form.title}
                onChange={(e) => setForm({ ...form, title: e.target.value })}
                placeholder="e.g. Rev B Prototype Passives & MCUs"
                className="w-full rounded-md border border-slate-300 px-3 py-1.5 text-sm"
              />
            </div>
            <div>
              <label className="mb-1 block text-xs font-medium text-slate-700">Project (Optional)</label>
              <select
                value={form.project}
                onChange={(e) => setForm({ ...form, project: e.target.value })}
                className="w-full rounded-md border border-slate-300 px-3 py-1.5 text-sm"
              >
                <option value="">None / General Stock</option>
                {(projectsData?.results ?? []).map((p) => (
                  <option key={p.id} value={p.id}>
                    {p.code} — {p.name}
                  </option>
                ))}
              </select>
            </div>
            <div>
              <label className="mb-1 block text-xs font-medium text-slate-700">Priority</label>
              <select
                value={form.priority}
                onChange={(e) => setForm({ ...form, priority: e.target.value as PurchasePriority })}
                className="w-full rounded-md border border-slate-300 px-3 py-1.5 text-sm"
              >
                <option value="LOW">LOW</option>
                <option value="NORMAL">NORMAL</option>
                <option value="HIGH">HIGH</option>
                <option value="URGENT">URGENT</option>
              </select>
            </div>
          </div>

          <div className="space-y-2">
            <div className="flex items-center justify-between">
              <span className="text-xs font-semibold uppercase text-slate-600">Requested Components *</span>
              <button
                type="button"
                onClick={() =>
                  setForm({
                    ...form,
                    lines: [...form.lines, { component: "", quantity: "10", estimated_unit_price: "", notes: "" }],
                  })
                }
                className="text-xs font-medium text-blue-700 hover:underline"
              >
                + Add Line
              </button>
            </div>
            {form.lines.map((line, idx) => (
              <div key={idx} className="grid grid-cols-12 items-center gap-2">
                <select
                  value={line.component}
                  onChange={(e) => {
                    const next = [...form.lines];
                    next[idx] = { ...next[idx], component: e.target.value };
                    setForm({ ...form, lines: next });
                  }}
                  className="col-span-6 rounded-md border border-slate-300 px-2 py-1.5 text-xs"
                >
                  <option value="">Select component...</option>
                  {(componentsData?.results ?? []).map((c) => (
                    <option key={c.id} value={c.id}>
                      {c.internal_part_number} — {c.mpn || c.name}
                    </option>
                  ))}
                </select>
                <input
                  type="number"
                  min="1"
                  value={line.quantity}
                  onChange={(e) => {
                    const next = [...form.lines];
                    next[idx] = { ...next[idx], quantity: e.target.value };
                    setForm({ ...form, lines: next });
                  }}
                  placeholder="Qty"
                  className="col-span-2 rounded-md border border-slate-300 px-2 py-1.5 text-xs font-mono"
                />
                <input
                  type="number"
                  step="0.0001"
                  min="0"
                  value={line.estimated_unit_price}
                  onChange={(e) => {
                    const next = [...form.lines];
                    next[idx] = { ...next[idx], estimated_unit_price: e.target.value };
                    setForm({ ...form, lines: next });
                  }}
                  placeholder="Est $"
                  className="col-span-3 rounded-md border border-slate-300 px-2 py-1.5 text-xs font-mono"
                />
                {form.lines.length > 1 && (
                  <button
                    type="button"
                    onClick={() => setForm({ ...form, lines: form.lines.filter((_, i) => i !== idx) })}
                    className="col-span-1 text-red-600 hover:text-red-700"
                  >
                    <Trash2 className="h-4 w-4" />
                  </button>
                )}
              </div>
            ))}
          </div>
        </div>
      </Modal>

      {/* Generate PR from BOM Shortage Modal */}
      <Modal
        open={openShortage}
        title="Generate Purchase Request from BOM Shortage"
        onClose={() => setOpenShortage(false)}
        footer={
          <>
            <Button variant="secondary" onClick={() => setOpenShortage(false)}>
              Cancel
            </Button>
            <Button
              loading={shortageMut.isPending}
              disabled={!shortageForm.bom_revision}
              onClick={() => shortageMut.mutate()}
            >
              Generate Shortage PR
            </Button>
          </>
        }
      >
        <div className="space-y-3">
          <div>
            <label className="mb-1 block text-xs font-medium text-slate-700">BOM Revision *</label>
            <select
              value={shortageForm.bom_revision}
              onChange={(e) => setShortageForm({ ...shortageForm, bom_revision: e.target.value })}
              className="w-full rounded-md border border-slate-300 px-3 py-1.5 text-sm"
            >
              <option value="">Select BOM revision...</option>
              {(revisionsData?.results ?? []).map((r) => (
                <option key={r.id} value={r.id}>
                  Revision #{r.id} — {r.revision_number} ({r.status})
                </option>
              ))}
            </select>
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="mb-1 block text-xs font-medium text-slate-700">Target Build Quantity *</label>
              <input
                type="number"
                min="1"
                value={shortageForm.build_quantity}
                onChange={(e) => setShortageForm({ ...shortageForm, build_quantity: e.target.value })}
                className="w-full rounded-md border border-slate-300 px-3 py-1.5 text-sm font-mono"
              />
            </div>
            <div>
              <label className="mb-1 block text-xs font-medium text-slate-700">Priority</label>
              <select
                value={shortageForm.priority}
                onChange={(e) => setShortageForm({ ...shortageForm, priority: e.target.value as PurchasePriority })}
                className="w-full rounded-md border border-slate-300 px-3 py-1.5 text-sm"
              >
                <option value="NORMAL">NORMAL</option>
                <option value="HIGH">HIGH</option>
                <option value="URGENT">URGENT</option>
              </select>
            </div>
          </div>
          <label className="flex items-center gap-2 text-sm">
            <input
              type="checkbox"
              checked={shortageForm.apply_moq}
              onChange={(e) => setShortageForm({ ...shortageForm, apply_moq: e.target.checked })}
            />
            Round shortage quantities up to supplier MOQ and order multiples
          </label>
        </div>
      </Modal>
    </div>
  );
}
