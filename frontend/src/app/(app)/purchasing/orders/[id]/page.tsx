"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { CheckCircle2, Lock, PackageCheck, Send, XCircle } from "lucide-react";
import Link from "next/link";
import { useParams } from "next/navigation";
import { useState } from "react";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import { Badge, Card, DescriptionList, ErrorState, Modal, PageHeader, Spinner } from "@/components/ui/primitives";
import { api, ApiError, type Paginated } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import type {
  GoodsReceipt,
  PurchaseOrder,
  PurchaseOrderStatus,
  Warehouse,
  WarehouseLocation,
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

export default function PurchaseOrderDetailPage() {
  const { id } = useParams<{ id: string }>();
  const qc = useQueryClient();
  const { can } = useAuth();

  const [openReceive, setOpenReceive] = useState(false);
  const [receiveWarehouse, setReceiveWarehouse] = useState("");
  const [deliveryNote, setDeliveryNote] = useState("");
  const [receiveNotes, setReceiveNotes] = useState("");
  const [idemKey, setIdemKey] = useState("");
  const [lineInputs, setLineInputs] = useState<
    Record<number, { qty: string; location: string; lot_batch: string }>
  >({});

  const { data: po, isLoading } = useQuery<PurchaseOrder>({
    queryKey: ["purchase-order", id],
    queryFn: () => api<PurchaseOrder>(`purchasing/orders/${id}`),
  });

  const { data: receiptsData } = useQuery<Paginated<GoodsReceipt>>({
    queryKey: ["goods-receipts", { purchase_order: id }],
    queryFn: () =>
      api<Paginated<GoodsReceipt>>("purchasing/goods-receipts", {
        query: { purchase_order: id, page_size: 50 },
      }),
  });

  const { data: warehousesData } = useQuery<Paginated<Warehouse>>({
    queryKey: ["warehouses", "active"],
    queryFn: () => api<Paginated<Warehouse>>("inventory/warehouses", { query: { page_size: 100 } }),
    enabled: openReceive,
  });

  const { data: locationsData } = useQuery<Paginated<WarehouseLocation>>({
    queryKey: ["warehouse-locations", receiveWarehouse],
    queryFn: () =>
      api<Paginated<WarehouseLocation>>("inventory/locations", {
        query: { warehouse: receiveWarehouse, page_size: 100 },
      }),
    enabled: openReceive && !!receiveWarehouse,
  });

  const actionMut = useMutation({
    mutationFn: (act: "approve" | "send" | "cancel" | "close") =>
      api(`purchasing/orders/${id}/${act}`, { method: "POST" }),
    onSuccess: (_, act) => {
      toast.success(`Purchase order ${act} completed`);
      qc.invalidateQueries({ queryKey: ["purchase-order", id] });
      qc.invalidateQueries({ queryKey: ["purchasing-orders"] });
    },
    onError: (e) => toast.error(e instanceof ApiError ? e.message : "Action failed"),
  });

  const receiveMut = useMutation({
    mutationFn: () => {
      const items = Object.entries(lineInputs)
        .filter(([, v]) => Number(v.qty) > 0)
        .map(([poiId, v]) => ({
          purchase_order_item: Number(poiId),
          quantity_received: v.qty,
          location: v.location ? Number(v.location) : null,
          lot_batch: v.lot_batch,
        }));
      return api<GoodsReceipt>(`purchasing/orders/${id}/receive`, {
        method: "POST",
        body: {
          warehouse: Number(receiveWarehouse),
          supplier_delivery_note: deliveryNote,
          idempotency_key: idemKey,
          notes: receiveNotes,
          items,
        },
      });
    },
    onSuccess: (grn) => {
      toast.success(`Goods Receipt ${grn.receipt_number} posted and inventory updated!`);
      setOpenReceive(false);
      qc.invalidateQueries({ queryKey: ["purchase-order", id] });
      qc.invalidateQueries({ queryKey: ["goods-receipts", { purchase_order: id }] });
      qc.invalidateQueries({ queryKey: ["purchasing-orders"] });
    },
    onError: (e) => toast.error(e instanceof ApiError ? e.message : "Failed to post goods receipt"),
  });

  if (isLoading) {
    return (
      <div className="flex justify-center py-12">
        <Spinner />
      </div>
    );
  }
  if (!po) return <ErrorState message="Purchase order not found." />;

  const canReceive =
    (po.status === "APPROVED" || po.status === "SENT" || po.status === "PARTIALLY_RECEIVED") &&
    can("purchase.receive");

  const startReceiving = () => {
    const initial: Record<number, { qty: string; location: string; lot_batch: string }> = {};
    for (const item of po.items) {
      const out = Number(item.quantity_outstanding);
      if (out > 0) {
        initial[item.id] = { qty: String(out), location: "", lot_batch: "" };
      }
    }
    setLineInputs(initial);
    setReceiveWarehouse(po.default_warehouse ? String(po.default_warehouse) : "");
    setDeliveryNote("");
    setReceiveNotes("");
    setIdemKey(`grn-${po.id}-${Date.now()}`);
    setOpenReceive(true);
  };

  const receipts = receiptsData?.results ?? [];

  return (
    <div className="space-y-6">
      <PageHeader
        title={
          <span className="flex items-center gap-2.5">
            <span className="pn">{po.po_number}</span>
            <span>{po.supplier_name}</span>
            <Badge tone={STATUS_TONE[po.status]}>{po.status}</Badge>
          </span>
        }
        subtitle={
          <>
            <Link href="/purchasing/orders" className="text-blue-700 hover:underline">
              Purchase Orders
            </Link>{" "}
            / Total: {Number(po.total_amount).toFixed(2)} {po.currency}
          </>
        }
        actions={
          <div className="flex flex-wrap gap-2">
            {po.status === "DRAFT" && can("purchase.approve") && (
              <Button loading={actionMut.isPending} onClick={() => actionMut.mutate("approve")}>
                <CheckCircle2 className="h-4 w-4" /> Approve PO
              </Button>
            )}
            {po.status === "APPROVED" && can("purchase.order") && (
              <Button loading={actionMut.isPending} onClick={() => actionMut.mutate("send")}>
                <Send className="h-4 w-4" /> Mark Sent to Supplier
              </Button>
            )}
            {canReceive && (
              <Button onClick={startReceiving}>
                <PackageCheck className="h-4 w-4" /> Receive Goods (GRN)
              </Button>
            )}
            {(po.status === "RECEIVED" || po.status === "PARTIALLY_RECEIVED") && can("purchase.order") && (
              <Button variant="secondary" loading={actionMut.isPending} onClick={() => actionMut.mutate("close")}>
                <Lock className="h-4 w-4" /> Close PO
              </Button>
            )}
            {(po.status === "DRAFT" || po.status === "APPROVED" || po.status === "SENT") &&
              can("purchase.order") && (
                <Button
                  variant="danger"
                  loading={actionMut.isPending}
                  onClick={() => {
                    if (confirm(`Cancel ${po.po_number}?`)) actionMut.mutate("cancel");
                  }}
                >
                  <XCircle className="h-4 w-4" /> Cancel
                </Button>
              )}
          </div>
        }
      />

      <div className="grid gap-6 lg:grid-cols-3">
        <div className="space-y-6 lg:col-span-2">
          <Card title={`Order Line Items (${po.items.length})`}>
            <div className="overflow-x-auto">
              <table className="w-full text-left text-sm">
                <thead className="border-b border-slate-200 text-xs uppercase text-slate-500">
                  <tr>
                    <th className="py-2 pr-3">Component</th>
                    <th className="py-2 pr-3">Supplier PN</th>
                    <th className="py-2 pr-3">Ordered</th>
                    <th className="py-2 pr-3">Received</th>
                    <th className="py-2 pr-3">Unit Price</th>
                    <th className="py-2 text-right">Line Total</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100">
                  {po.items.map((item) => {
                    const ordered = Number(item.quantity_ordered);
                    const received = Number(item.quantity_received);
                    const pct = ordered > 0 ? Math.min(100, Math.round((received / ordered) * 100)) : 0;
                    return (
                      <tr key={item.id}>
                        <td className="py-2.5 pr-3">
                          <Link
                            href={`/components/${item.component}`}
                            className="font-mono text-xs font-semibold text-blue-700 hover:underline"
                          >
                            {item.component_internal_part_number}
                          </Link>
                          <div className="text-xs text-slate-500">{item.mpn_snapshot || item.component_name}</div>
                        </td>
                        <td className="py-2.5 pr-3 font-mono text-xs text-slate-600">
                          {item.supplier_part_number_snapshot || "—"}
                        </td>
                        <td className="py-2.5 pr-3 font-mono text-xs font-semibold">{ordered}</td>
                        <td className="py-2.5 pr-3">
                          <div className="flex items-center gap-2">
                            <span className="font-mono text-xs font-semibold">
                              {received} / {ordered}
                            </span>
                            <Badge tone={received >= ordered ? "green" : received > 0 ? "blue" : "slate"}>
                              {pct}%
                            </Badge>
                          </div>
                        </td>
                        <td className="py-2.5 pr-3 font-mono text-xs">
                          {Number(item.unit_price).toFixed(4)} {po.currency}
                        </td>
                        <td className="py-2.5 text-right font-mono text-xs font-semibold">
                          {Number(item.line_total).toFixed(2)} {po.currency}
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          </Card>

          <Card title={`Goods Receipts (${receipts.length})`}>
            {receipts.length === 0 ? (
              <p className="text-sm text-slate-500">No goods receipts posted against this purchase order yet.</p>
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full text-left text-sm">
                  <thead className="border-b border-slate-200 text-xs uppercase text-slate-500">
                    <tr>
                      <th className="py-2 pr-3">GRN #</th>
                      <th className="py-2 pr-3">Warehouse</th>
                      <th className="py-2 pr-3">Delivery Note</th>
                      <th className="py-2 pr-3">Received By</th>
                      <th className="py-2 pr-3">Received At</th>
                      <th className="py-2 text-right">Status</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-100">
                    {receipts.map((grn) => (
                      <tr key={grn.id}>
                        <td className="py-2 pr-3 font-mono text-xs font-semibold text-slate-900">
                          {grn.receipt_number}
                        </td>
                        <td className="py-2 pr-3 text-xs">{grn.warehouse_code}</td>
                        <td className="py-2 pr-3 text-xs text-slate-600">{grn.supplier_delivery_note || "—"}</td>
                        <td className="py-2 pr-3 text-xs">{grn.received_by_name || "—"}</td>
                        <td className="py-2 pr-3 text-xs text-slate-500">
                          {grn.received_at ? formatDateTime(grn.received_at) : "—"}
                        </td>
                        <td className="py-2 text-right">
                          <Badge tone="green">{grn.status}</Badge>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </Card>
        </div>

        <div className="space-y-6">
          <Card title="Financial Summary">
            <DescriptionList
              items={[
                { label: "Currency", value: `${po.currency} (Rate: ${Number(po.exchange_rate).toFixed(4)})` },
                { label: "Subtotal", value: `${Number(po.subtotal).toFixed(2)} ${po.currency}` },
                { label: "Tax", value: `${Number(po.tax_amount).toFixed(2)} ${po.currency}` },
                { label: "Shipping", value: `${Number(po.shipping_amount).toFixed(2)} ${po.currency}` },
                { label: "Discount", value: `-${Number(po.discount_amount).toFixed(2)} ${po.currency}` },
                {
                  label: "Total Amount",
                  value: (
                    <span className="font-mono text-base font-bold text-slate-900">
                      {Number(po.total_amount).toFixed(2)} {po.currency}
                    </span>
                  ),
                },
                { label: "Payment Terms", value: po.payment_terms_snapshot || "—" },
              ]}
            />
          </Card>

          <Card title="Order Metadata">
            <DescriptionList
              items={[
                {
                  label: "Supplier",
                  value: (
                    <Link href={`/suppliers/${po.supplier}`} className="text-blue-700 hover:underline">
                      {po.supplier_code} — {po.supplier_name}
                    </Link>
                  ),
                },
                {
                  label: "Source PR",
                  value: po.purchase_request ? (
                    <Link href={`/purchasing/requests/${po.purchase_request}`} className="text-blue-700 hover:underline">
                      {po.purchase_request_number}
                    </Link>
                  ) : (
                    "Direct PO"
                  ),
                },
                { label: "Default Warehouse", value: po.default_warehouse_code || "—" },
                { label: "Approved By", value: po.approved_by_name || "—" },
                { label: "Sent By", value: po.sent_by_name || "—" },
                { label: "Created At", value: formatDateTime(po.created_at) },
              ]}
            />
          </Card>
        </div>
      </div>

      {/* Receive Goods Modal */}
      <Modal
        open={openReceive}
        title={`Receive Goods Against ${po.po_number}`}
        onClose={() => setOpenReceive(false)}
        footer={
          <>
            <Button variant="secondary" onClick={() => setOpenReceive(false)}>
              Cancel
            </Button>
            <Button
              loading={receiveMut.isPending}
              disabled={
                !receiveWarehouse ||
                Object.values(lineInputs).every((v) => !v.qty || Number(v.qty) <= 0)
              }
              onClick={() => receiveMut.mutate()}
            >
              Post Goods Receipt & Increment Stock
            </Button>
          </>
        }
      >
        <div className="space-y-4">
          <div className="grid gap-3 sm:grid-cols-2">
            <div>
              <label className="mb-1 block text-xs font-medium text-slate-700">Receiving Warehouse *</label>
              <select
                value={receiveWarehouse}
                onChange={(e) => setReceiveWarehouse(e.target.value)}
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
              <label className="mb-1 block text-xs font-medium text-slate-700">Supplier Delivery Note / Waybill</label>
              <input
                type="text"
                value={deliveryNote}
                onChange={(e) => setDeliveryNote(e.target.value)}
                placeholder="e.g. DN-2026-884"
                className="w-full rounded-md border border-slate-300 px-3 py-1.5 text-sm"
              />
            </div>
          </div>

          <div className="space-y-2">
            <div className="text-xs font-semibold uppercase text-slate-600">Outstanding PO Lines</div>
            {po.items
              .filter((item) => Number(item.quantity_outstanding) > 0)
              .map((item) => {
                const state = lineInputs[item.id] ?? { qty: "0", location: "", lot_batch: "" };
                return (
                  <div key={item.id} className="rounded-md border border-slate-200 p-3 text-xs">
                    <div className="mb-2 flex items-center justify-between font-medium">
                      <span>
                        <span className="font-mono text-blue-700">{item.component_internal_part_number}</span> —{" "}
                        {item.mpn_snapshot || item.component_name}
                      </span>
                      <span className="font-mono text-slate-500">
                        Outstanding: {Number(item.quantity_outstanding)}
                      </span>
                    </div>
                    <div className="grid grid-cols-3 gap-2">
                      <div>
                        <label className="mb-0.5 block text-[11px] text-slate-500">Qty to Receive *</label>
                        <input
                          type="number"
                          min="0"
                          max={Number(item.quantity_outstanding)}
                          value={state.qty}
                          onChange={(e) =>
                            setLineInputs({
                              ...lineInputs,
                              [item.id]: { ...state, qty: e.target.value },
                            })
                          }
                          className="w-full rounded border border-slate-300 px-2 py-1 font-mono"
                        />
                      </div>
                      <div>
                        <label className="mb-0.5 block text-[11px] text-slate-500">Bin Location</label>
                        <select
                          value={state.location}
                          onChange={(e) =>
                            setLineInputs({
                              ...lineInputs,
                              [item.id]: { ...state, location: e.target.value },
                            })
                          }
                          className="w-full rounded border border-slate-300 px-2 py-1"
                        >
                          <option value="">Unassigned</option>
                          {(locationsData?.results ?? []).map((loc) => (
                            <option key={loc.id} value={loc.id}>
                              {loc.code}
                            </option>
                          ))}
                        </select>
                      </div>
                      <div>
                        <label className="mb-0.5 block text-[11px] text-slate-500">Lot / Date Code</label>
                        <input
                          type="text"
                          value={state.lot_batch}
                          onChange={(e) =>
                            setLineInputs({
                              ...lineInputs,
                              [item.id]: { ...state, lot_batch: e.target.value },
                            })
                          }
                          placeholder="LOT-2026"
                          className="w-full rounded border border-slate-300 px-2 py-1 font-mono"
                        />
                      </div>
                    </div>
                  </div>
                );
              })}
          </div>
        </div>
      </Modal>
    </div>
  );
}
