"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Plus, Search, Trash2 } from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import { Badge, Card, EmptyState, ErrorState, Modal, PageHeader, Spinner } from "@/components/ui/primitives";
import { api, ApiError, type Paginated } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import type {
  ComponentListItem,
  Project,
  PurchaseOrder,
  PurchaseOrderStatus,
  Supplier,
  Warehouse,
} from "@/lib/types";
import { formatDateTime } from "@/lib/utils";

const STATUS_TONE: Record<PurchaseOrderStatus, "slate" | "amber" | "blue" | "green" | "red"> = {
  DRAFT: "slate",
  APPROVED: "amber",
  SENT: "blue",
  PARTIALLY_RECEIVED: "blue",
  RECEIVED: "green",
  CLOSED: "green",
  CANCELLED: "red",
};

export default function PurchaseOrdersPage() {
  const { can } = useAuth();
  const router = useRouter();
  const qc = useQueryClient();

  const [search, setSearch] = useState("");
  const [statusFilter, setStatusFilter] = useState("");
  const [openCreate, setOpenCreate] = useState(false);

  const [form, setForm] = useState({
    supplier: "",
    project: "",
    default_warehouse: "",
    currency: "USD",
    exchange_rate: "1.000000",
    tax_amount: "0.00",
    shipping_amount: "0.00",
    discount_amount: "0.00",
    expected_delivery_date: "",
    notes: "",
    lines: [{ component: "", quantity_ordered: "10", unit_price: "0.1000" }],
  });

  const { data, isLoading, error } = useQuery<Paginated<PurchaseOrder>>({
    queryKey: ["purchasing-orders", search, statusFilter],
    queryFn: () =>
      api<Paginated<PurchaseOrder>>("purchasing/orders", {
        query: {
          search: search || undefined,
          status: statusFilter || undefined,
          page_size: 100,
        },
      }),
  });

  const { data: suppliersData } = useQuery<Paginated<Supplier>>({
    queryKey: ["suppliers", "active"],
    queryFn: () => api<Paginated<Supplier>>("suppliers", { query: { status: "ACTIVE", page_size: 100 } }),
    enabled: openCreate,
  });

  const { data: warehousesData } = useQuery<Paginated<Warehouse>>({
    queryKey: ["warehouses", "active"],
    queryFn: () => api<Paginated<Warehouse>>("inventory/warehouses", { query: { page_size: 100 } }),
    enabled: openCreate,
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

  const createMut = useMutation({
    mutationFn: () =>
      api<PurchaseOrder>("purchasing/orders", {
        method: "POST",
        body: {
          supplier: Number(form.supplier),
          project: form.project ? Number(form.project) : null,
          default_warehouse: form.default_warehouse ? Number(form.default_warehouse) : null,
          currency: form.currency,
          exchange_rate: form.exchange_rate,
          tax_amount: form.tax_amount || "0",
          shipping_amount: form.shipping_amount || "0",
          discount_amount: form.discount_amount || "0",
          expected_delivery_date: form.expected_delivery_date || null,
          notes: form.notes,
          items: form.lines
            .filter((l) => l.component && Number(l.quantity_ordered) > 0)
            .map((l) => ({
              component: Number(l.component),
              quantity_ordered: l.quantity_ordered,
              unit_price: l.unit_price || "0",
            })),
        },
      }),
    onSuccess: (created) => {
      toast.success(`Purchase Order ${created.po_number} created`);
      setOpenCreate(false);
      qc.invalidateQueries({ queryKey: ["purchasing-orders"] });
      router.push(`/purchasing/orders/${created.id}`);
    },
    onError: (e) => toast.error(e instanceof ApiError ? e.message : "Failed to create purchase order"),
  });

  const orders = data?.results ?? [];

  return (
    <div className="space-y-6">
      <PageHeader
        title="Purchase Orders"
        subtitle="Controlled supplier orders with currency snapshots, Decimal totals, and receiving progress."
        actions={
          can("purchase.order") && (
            <Button onClick={() => setOpenCreate(true)}>
              <Plus className="h-4 w-4" /> New Purchase Order
            </Button>
          )
        }
      />

      <Card>
        <div className="flex flex-wrap items-center gap-3">
          <div className="relative min-w-[240px] flex-1">
            <Search className="pointer-events-none absolute left-3 top-2.5 h-4 w-4 text-slate-400" />
            <input
              type="text"
              placeholder="Search by PO #, supplier, project..."
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
            <option value="APPROVED">Approved</option>
            <option value="SENT">Sent</option>
            <option value="PARTIALLY_RECEIVED">Partially Received</option>
            <option value="RECEIVED">Received</option>
            <option value="CLOSED">Closed</option>
            <option value="CANCELLED">Cancelled</option>
          </select>
        </div>
      </Card>

      {isLoading ? (
        <div className="flex justify-center py-12">
          <Spinner />
        </div>
      ) : error ? (
        <ErrorState message="Failed to load purchase orders." />
      ) : orders.length === 0 ? (
        <EmptyState
          title="No purchase orders"
          description="Create a purchase order directly or convert an approved purchase request."
          action={
            can("purchase.order") && (
              <Button onClick={() => setOpenCreate(true)}>
                <Plus className="h-4 w-4" /> New Purchase Order
              </Button>
            )
          }
        />
      ) : (
        <div className="overflow-x-auto rounded-lg border border-slate-200 bg-white shadow-sm">
          <table className="w-full text-left text-sm">
            <thead className="border-b border-slate-200 bg-slate-50 text-xs font-semibold uppercase text-slate-600">
              <tr>
                <th className="px-4 py-3">PO #</th>
                <th className="px-4 py-3">Supplier</th>
                <th className="px-4 py-3">Project / PR</th>
                <th className="px-4 py-3">Lines</th>
                <th className="px-4 py-3">Total Amount</th>
                <th className="px-4 py-3">Status</th>
                <th className="px-4 py-3">Created</th>
                <th className="px-4 py-3 text-right">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {orders.map((po) => (
                <tr key={po.id} className="hover:bg-slate-50">
                  <td className="px-4 py-3 font-mono text-xs font-semibold text-blue-700">
                    <Link href={`/purchasing/orders/${po.id}`} className="hover:underline">
                      {po.po_number}
                    </Link>
                  </td>
                  <td className="px-4 py-3 font-medium text-slate-900">
                    <Link href={`/suppliers/${po.supplier}`} className="hover:text-blue-700 hover:underline">
                      {po.supplier_name}
                    </Link>
                    <div className="font-mono text-xs text-slate-400">{po.supplier_code}</div>
                  </td>
                  <td className="px-4 py-3 text-xs text-slate-600">
                    {po.project_code ? `${po.project_code} — ${po.project_name}` : "General"}
                    {po.purchase_request_number && (
                      <div className="font-mono text-slate-400">From {po.purchase_request_number}</div>
                    )}
                  </td>
                  <td className="px-4 py-3 font-mono text-xs">{po.item_count}</td>
                  <td className="px-4 py-3 font-mono text-xs font-semibold">
                    {Number(po.total_amount).toFixed(2)} {po.currency}
                  </td>
                  <td className="px-4 py-3">
                    <Badge tone={STATUS_TONE[po.status]}>{po.status}</Badge>
                  </td>
                  <td className="px-4 py-3 text-xs text-slate-500">{formatDateTime(po.created_at)}</td>
                  <td className="px-4 py-3 text-right">
                    <Link
                      href={`/purchasing/orders/${po.id}`}
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

      {/* Create Purchase Order Modal */}
      <Modal
        open={openCreate}
        title="New Purchase Order"
        onClose={() => setOpenCreate(false)}
        footer={
          <>
            <Button variant="secondary" onClick={() => setOpenCreate(false)}>
              Cancel
            </Button>
            <Button
              loading={createMut.isPending}
              disabled={!form.supplier || form.lines.every((l) => !l.component)}
              onClick={() => createMut.mutate()}
            >
              Create Purchase Order
            </Button>
          </>
        }
      >
        <div className="space-y-4">
          <div className="grid gap-3 sm:grid-cols-2">
            <div>
              <label className="mb-1 block text-xs font-medium text-slate-700">Supplier *</label>
              <select
                value={form.supplier}
                onChange={(e) => {
                  const sup = (suppliersData?.results ?? []).find((s) => String(s.id) === e.target.value);
                  setForm({
                    ...form,
                    supplier: e.target.value,
                    currency: sup?.currency || form.currency,
                  });
                }}
                className="w-full rounded-md border border-slate-300 px-3 py-1.5 text-sm"
              >
                <option value="">Select active supplier...</option>
                {(suppliersData?.results ?? []).map((s) => (
                  <option key={s.id} value={s.id}>
                    {s.code} — {s.name} ({s.currency})
                  </option>
                ))}
              </select>
            </div>
            <div>
              <label className="mb-1 block text-xs font-medium text-slate-700">Default Warehouse</label>
              <select
                value={form.default_warehouse}
                onChange={(e) => setForm({ ...form, default_warehouse: e.target.value })}
                className="w-full rounded-md border border-slate-300 px-3 py-1.5 text-sm"
              >
                <option value="">Select warehouse...</option>
                {(warehousesData?.results ?? []).map((w) => (
                  <option key={w.id} value={w.id}>
                    {w.code} — {w.name}
                  </option>
                ))}
              </select>
            </div>
            <div>
              <label className="mb-1 block text-xs font-medium text-slate-700">Project (Optional)</label>
              <select
                value={form.project}
                onChange={(e) => setForm({ ...form, project: e.target.value })}
                className="w-full rounded-md border border-slate-300 px-3 py-1.5 text-sm"
              >
                <option value="">None</option>
                {(projectsData?.results ?? []).map((p) => (
                  <option key={p.id} value={p.id}>
                    {p.code} — {p.name}
                  </option>
                ))}
              </select>
            </div>
            <div>
              <label className="mb-1 block text-xs font-medium text-slate-700">Currency & Exchange Rate</label>
              <div className="grid grid-cols-2 gap-2">
                <input
                  type="text"
                  maxLength={3}
                  value={form.currency}
                  onChange={(e) => setForm({ ...form, currency: e.target.value.toUpperCase() })}
                  className="rounded-md border border-slate-300 px-2 py-1.5 text-sm font-mono uppercase"
                />
                <input
                  type="number"
                  step="0.0001"
                  min="0.0001"
                  value={form.exchange_rate}
                  onChange={(e) => setForm({ ...form, exchange_rate: e.target.value })}
                  className="rounded-md border border-slate-300 px-2 py-1.5 text-sm font-mono"
                />
              </div>
            </div>
          </div>

          <div className="space-y-2">
            <div className="flex items-center justify-between">
              <span className="text-xs font-semibold uppercase text-slate-600">PO Line Items *</span>
              <button
                type="button"
                onClick={() =>
                  setForm({
                    ...form,
                    lines: [...form.lines, { component: "", quantity_ordered: "10", unit_price: "0.1000" }],
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
                  value={line.quantity_ordered}
                  onChange={(e) => {
                    const next = [...form.lines];
                    next[idx] = { ...next[idx], quantity_ordered: e.target.value };
                    setForm({ ...form, lines: next });
                  }}
                  placeholder="Qty"
                  className="col-span-2 rounded-md border border-slate-300 px-2 py-1.5 text-xs font-mono"
                />
                <input
                  type="number"
                  step="0.0001"
                  min="0"
                  value={line.unit_price}
                  onChange={(e) => {
                    const next = [...form.lines];
                    next[idx] = { ...next[idx], unit_price: e.target.value };
                    setForm({ ...form, lines: next });
                  }}
                  placeholder="Unit $"
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
    </div>
  );
}
