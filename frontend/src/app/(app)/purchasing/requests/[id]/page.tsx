"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { CheckCircle2, Send, ShoppingCart, XCircle } from "lucide-react";
import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { useState } from "react";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import { Badge, Card, DescriptionList, ErrorState, Modal, PageHeader, Spinner } from "@/components/ui/primitives";
import { api, ApiError, type Paginated } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import type {
  PurchaseOrder,
  PurchaseRequest,
  PurchaseRequestStatus,
  Supplier,
  Warehouse,
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

export default function PurchaseRequestDetailPage() {
  const { id } = useParams<{ id: string }>();
  const router = useRouter();
  const qc = useQueryClient();
  const { can } = useAuth();

  const [reviewAction, setReviewAction] = useState<"approve" | "reject" | null>(null);
  const [reviewNotes, setReviewNotes] = useState("");
  const [openConvertPO, setOpenConvertPO] = useState(false);

  const [poForm, setPoForm] = useState({
    supplier: "",
    default_warehouse: "",
    currency: "USD",
    exchange_rate: "1.000000",
    apply_moq: true,
    notes: "",
  });

  const { data: pr, isLoading } = useQuery<PurchaseRequest>({
    queryKey: ["purchase-request", id],
    queryFn: () => api<PurchaseRequest>(`purchasing/requests/${id}`),
  });

  const { data: suppliersData } = useQuery<Paginated<Supplier>>({
    queryKey: ["suppliers", "active"],
    queryFn: () => api<Paginated<Supplier>>("suppliers", { query: { status: "ACTIVE", page_size: 100 } }),
    enabled: openConvertPO,
  });

  const { data: warehousesData } = useQuery<Paginated<Warehouse>>({
    queryKey: ["warehouses", "active"],
    queryFn: () => api<Paginated<Warehouse>>("inventory/warehouses", { query: { page_size: 100 } }),
    enabled: openConvertPO,
  });

  const submitMut = useMutation({
    mutationFn: () => api(`purchasing/requests/${id}/submit`, { method: "POST" }),
    onSuccess: () => {
      toast.success("Purchase request submitted for approval");
      qc.invalidateQueries({ queryKey: ["purchase-request", id] });
      qc.invalidateQueries({ queryKey: ["purchasing-requests"] });
    },
    onError: (e) => toast.error(e instanceof ApiError ? e.message : "Failed to submit"),
  });

  const reviewMut = useMutation({
    mutationFn: (act: "approve" | "reject") =>
      api(`purchasing/requests/${id}/${act}`, {
        method: "POST",
        body: { notes: reviewNotes },
      }),
    onSuccess: (_, act) => {
      toast.success(`Purchase request ${act === "approve" ? "approved" : "rejected"}`);
      setReviewAction(null);
      setReviewNotes("");
      qc.invalidateQueries({ queryKey: ["purchase-request", id] });
      qc.invalidateQueries({ queryKey: ["purchasing-requests"] });
    },
    onError: (e) => toast.error(e instanceof ApiError ? e.message : "Review action failed"),
  });

  const convertPOMut = useMutation({
    mutationFn: () =>
      api<PurchaseOrder>(`purchasing/requests/${id}/create-po`, {
        method: "POST",
        body: {
          supplier: Number(poForm.supplier),
          default_warehouse: poForm.default_warehouse ? Number(poForm.default_warehouse) : null,
          currency: poForm.currency,
          exchange_rate: poForm.exchange_rate,
          apply_moq: poForm.apply_moq,
          notes: poForm.notes,
        },
      }),
    onSuccess: (po) => {
      toast.success(`Purchase Order ${po.po_number} created`);
      setOpenConvertPO(false);
      router.push(`/purchasing/orders/${po.id}`);
    },
    onError: (e) => toast.error(e instanceof ApiError ? e.message : "Failed to convert to PO"),
  });

  if (isLoading) {
    return (
      <div className="flex justify-center py-12">
        <Spinner />
      </div>
    );
  }
  if (!pr) return <ErrorState message="Purchase request not found." />;

  const canReview = (pr.status === "DRAFT" || pr.status === "SUBMITTED") && can("purchase.approve");
  const canConvert = (pr.status === "APPROVED" || pr.status === "ORDERED") && can("purchase.order");

  return (
    <div className="space-y-6">
      <PageHeader
        title={
          <span className="flex items-center gap-2.5">
            <span className="pn">{pr.request_number}</span>
            <span>{pr.title}</span>
            <Badge tone={STATUS_TONE[pr.status]}>{pr.status}</Badge>
          </span>
        }
        subtitle={
          <>
            <Link href="/purchasing/requests" className="text-blue-700 hover:underline">
              Purchase Requests
            </Link>{" "}
            / Priority: {pr.priority} · Est. Total: ${Number(pr.estimated_total).toFixed(2)}
          </>
        }
        actions={
          <div className="flex flex-wrap gap-2">
            {pr.status === "DRAFT" && can("purchase.create") && (
              <Button loading={submitMut.isPending} onClick={() => submitMut.mutate()}>
                <Send className="h-4 w-4" /> Submit for Approval
              </Button>
            )}
            {canReview && (
              <>
                <Button onClick={() => setReviewAction("approve")}>
                  <CheckCircle2 className="h-4 w-4" /> Approve
                </Button>
                <Button variant="danger" onClick={() => setReviewAction("reject")}>
                  <XCircle className="h-4 w-4" /> Reject
                </Button>
              </>
            )}
            {canConvert && (
              <Button
                onClick={() => {
                  const firstPreferred = pr.items.find((i) => i.preferred_supplier)?.preferred_supplier;
                  setPoForm((prev) => ({
                    ...prev,
                    supplier: firstPreferred ? String(firstPreferred) : prev.supplier,
                  }));
                  setOpenConvertPO(true);
                }}
              >
                <ShoppingCart className="h-4 w-4" /> Create Purchase Order
              </Button>
            )}
          </div>
        }
      />

      <div className="grid gap-6 lg:grid-cols-3">
        <div className="space-y-6 lg:col-span-2">
          <Card title={`Requested Line Items (${pr.items.length})`}>
            <div className="overflow-x-auto">
              <table className="w-full text-left text-sm">
                <thead className="border-b border-slate-200 text-xs uppercase text-slate-500">
                  <tr>
                    <th className="py-2 pr-3">Component</th>
                    <th className="py-2 pr-3">Preferred Supplier</th>
                    <th className="py-2 pr-3">Quantity</th>
                    <th className="py-2 pr-3">Est. Unit Price</th>
                    <th className="py-2 text-right">Est. Line Total</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100">
                  {pr.items.map((item) => {
                    const ext = item.estimated_unit_price
                      ? (Number(item.quantity) * Number(item.estimated_unit_price)).toFixed(2)
                      : null;
                    return (
                      <tr key={item.id}>
                        <td className="py-2.5 pr-3">
                          <Link
                            href={`/components/${item.component}`}
                            className="font-mono text-xs font-semibold text-blue-700 hover:underline"
                          >
                            {item.component_internal_part_number}
                          </Link>
                          <div className="text-xs text-slate-500">{item.component_mpn || item.component_name}</div>
                        </td>
                        <td className="py-2.5 pr-3 text-xs">
                          {item.preferred_supplier_name ? (
                            <>
                              <div className="font-medium text-slate-900">{item.preferred_supplier_name}</div>
                              {item.supplier_part_number && (
                                <div className="font-mono text-slate-500">{item.supplier_part_number}</div>
                              )}
                            </>
                          ) : (
                            <span className="text-slate-400">Any approved supplier</span>
                          )}
                        </td>
                        <td className="py-2.5 pr-3 font-mono text-xs font-semibold">{Number(item.quantity)}</td>
                        <td className="py-2.5 pr-3 font-mono text-xs">
                          {item.estimated_unit_price
                            ? `${Number(item.estimated_unit_price).toFixed(4)} ${item.currency}`
                            : "—"}
                        </td>
                        <td className="py-2.5 text-right font-mono text-xs font-semibold">
                          {ext ? `${ext} ${item.currency}` : "—"}
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          </Card>
        </div>

        <div className="space-y-6">
          <Card title="Request Metadata">
            <DescriptionList
              items={[
                { label: "Request Number", value: <span className="pn">{pr.request_number}</span> },
                { label: "Status", value: <Badge tone={STATUS_TONE[pr.status]}>{pr.status}</Badge> },
                { label: "Priority", value: pr.priority },
                {
                  label: "Project",
                  value: pr.project ? (
                    <Link href={`/projects/${pr.project}`} className="text-blue-700 hover:underline">
                      {pr.project_code} — {pr.project_name}
                    </Link>
                  ) : (
                    "General Inventory"
                  ),
                },
                {
                  label: "BOM Revision",
                  value: pr.bom_revision ? (
                    <Link href={`/bom-revisions/${pr.bom_revision}`} className="text-blue-700 hover:underline">
                      {pr.bom_revision_label} (x{Number(pr.build_quantity)})
                    </Link>
                  ) : (
                    "—"
                  ),
                },
                { label: "Created By", value: pr.created_by_name || "—" },
                { label: "Created At", value: formatDateTime(pr.created_at) },
                { label: "Submitted By", value: pr.submitted_by_name || "—" },
                { label: "Reviewed By", value: pr.reviewed_by_name || "—" },
                { label: "Review Notes", value: pr.review_notes || "—" },
              ]}
            />
          </Card>
        </div>
      </div>

      {/* Approve / Reject Modal */}
      <Modal
        open={!!reviewAction}
        title={reviewAction === "approve" ? `Approve ${pr.request_number}` : `Reject ${pr.request_number}`}
        onClose={() => setReviewAction(null)}
        footer={
          <>
            <Button variant="secondary" onClick={() => setReviewAction(null)}>
              Cancel
            </Button>
            <Button
              variant={reviewAction === "reject" ? "danger" : "primary"}
              loading={reviewMut.isPending}
              onClick={() => reviewAction && reviewMut.mutate(reviewAction)}
            >
              {reviewAction === "approve" ? "Confirm Approval" : "Confirm Rejection"}
            </Button>
          </>
        }
      >
        <div>
          <label className="mb-1 block text-xs font-medium text-slate-700">Review Notes</label>
          <textarea
            rows={3}
            value={reviewNotes}
            onChange={(e) => setReviewNotes(e.target.value)}
            placeholder="Optional approval or rejection notes..."
            className="w-full rounded-md border border-slate-300 px-3 py-1.5 text-sm"
          />
        </div>
      </Modal>

      {/* Convert PR to PO Modal */}
      <Modal
        open={openConvertPO}
        title={`Create Purchase Order from ${pr.request_number}`}
        onClose={() => setOpenConvertPO(false)}
        footer={
          <>
            <Button variant="secondary" onClick={() => setOpenConvertPO(false)}>
              Cancel
            </Button>
            <Button
              loading={convertPOMut.isPending}
              disabled={!poForm.supplier}
              onClick={() => convertPOMut.mutate()}
            >
              Create Purchase Order
            </Button>
          </>
        }
      >
        <div className="space-y-3">
          <div>
            <label className="mb-1 block text-xs font-medium text-slate-700">Supplier *</label>
            <select
              value={poForm.supplier}
              onChange={(e) => setPoForm({ ...poForm, supplier: e.target.value })}
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
            <label className="mb-1 block text-xs font-medium text-slate-700">Default Receiving Warehouse</label>
            <select
              value={poForm.default_warehouse}
              onChange={(e) => setPoForm({ ...poForm, default_warehouse: e.target.value })}
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
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="mb-1 block text-xs font-medium text-slate-700">Currency</label>
              <input
                type="text"
                maxLength={3}
                value={poForm.currency}
                onChange={(e) => setPoForm({ ...poForm, currency: e.target.value.toUpperCase() })}
                className="w-full rounded-md border border-slate-300 px-3 py-1.5 text-sm font-mono uppercase"
              />
            </div>
            <div>
              <label className="mb-1 block text-xs font-medium text-slate-700">Exchange Rate</label>
              <input
                type="number"
                step="0.0001"
                min="0.0001"
                value={poForm.exchange_rate}
                onChange={(e) => setPoForm({ ...poForm, exchange_rate: e.target.value })}
                className="w-full rounded-md border border-slate-300 px-3 py-1.5 text-sm font-mono"
              />
            </div>
          </div>
          <label className="flex items-center gap-2 text-sm">
            <input
              type="checkbox"
              checked={poForm.apply_moq}
              onChange={(e) => setPoForm({ ...poForm, apply_moq: e.target.checked })}
            />
            Enforce supplier MOQ and order multiples on PO lines
          </label>
        </div>
      </Modal>
    </div>
  );
}
