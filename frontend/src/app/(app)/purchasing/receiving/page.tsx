"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { PackageCheck } from "lucide-react";
import Link from "next/link";
import { useState } from "react";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import { Badge, Card, EmptyState, ErrorState, PageHeader, Spinner } from "@/components/ui/primitives";
import { api, ApiError, type Paginated } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import type { GoodsReceipt, PurchaseOrder, Warehouse, WarehouseLocation } from "@/lib/types";
import { formatDateTime } from "@/lib/utils";

export default function GoodsReceivingPage() {
  const { can } = useAuth();
  const qc = useQueryClient();

  const [selectedPoId, setSelectedPoId] = useState("");
  const [warehouseId, setWarehouseId] = useState("");
  const [deliveryNote, setDeliveryNote] = useState("");
  const [notes, setNotes] = useState("");
  const [lineInputs, setLineInputs] = useState<
    Record<number, { qty: string; location: string; lot_batch: string }>
  >({});

  const { data: receiptsData, isLoading, error } = useQuery<Paginated<GoodsReceipt>>({
    queryKey: ["goods-receipts"],
    queryFn: () => api<Paginated<GoodsReceipt>>("purchasing/goods-receipts", { query: { page_size: 100 } }),
  });

  const { data: openOrdersData } = useQuery<Paginated<PurchaseOrder>>({
    queryKey: ["purchasing-orders", "receivable"],
    queryFn: () => api<Paginated<PurchaseOrder>>("purchasing/orders", { query: { page_size: 100 } }),
    enabled: can("purchase.receive"),
  });

  const { data: warehousesData } = useQuery<Paginated<Warehouse>>({
    queryKey: ["warehouses", "active"],
    queryFn: () => api<Paginated<Warehouse>>("inventory/warehouses", { query: { page_size: 100 } }),
    enabled: can("purchase.receive"),
  });

  const { data: locationsData } = useQuery<Paginated<WarehouseLocation>>({
    queryKey: ["warehouse-locations", warehouseId],
    queryFn: () =>
      api<Paginated<WarehouseLocation>>("inventory/locations", {
        query: { warehouse: warehouseId, page_size: 100 },
      }),
    enabled: !!warehouseId,
  });

  const receivableOrders = (openOrdersData?.results ?? []).filter(
    (po) => po.status === "APPROVED" || po.status === "SENT" || po.status === "PARTIALLY_RECEIVED"
  );

  const selectedPo = receivableOrders.find((po) => String(po.id) === selectedPoId) ?? null;

  const handleSelectPo = (poId: string) => {
    setSelectedPoId(poId);
    const found = receivableOrders.find((po) => String(po.id) === poId);
    if (!found) {
      setLineInputs({});
      return;
    }
    if (found.default_warehouse) {
      setWarehouseId(String(found.default_warehouse));
    }
    const init: Record<number, { qty: string; location: string; lot_batch: string }> = {};
    for (const item of found.items) {
      const out = Number(item.quantity_outstanding);
      if (out > 0) {
        init[item.id] = { qty: String(out), location: "", lot_batch: "" };
      }
    }
    setLineInputs(init);
  };

  const postReceiptMut = useMutation({
    mutationFn: () => {
      const items = Object.entries(lineInputs)
        .filter(([, v]) => Number(v.qty) > 0)
        .map(([poiId, v]) => ({
          purchase_order_item: Number(poiId),
          quantity_received: v.qty,
          location: v.location ? Number(v.location) : null,
          lot_batch: v.lot_batch,
        }));
      return api<GoodsReceipt>("purchasing/goods-receipts", {
        method: "POST",
        body: {
          purchase_order: Number(selectedPoId),
          warehouse: Number(warehouseId),
          supplier_delivery_note: deliveryNote,
          idempotency_key: `grn-desk-${selectedPoId}-${Date.now()}`,
          notes,
          items,
        },
      });
    },
    onSuccess: (grn) => {
      toast.success(`Posted ${grn.receipt_number} — inventory balances updated atomically!`);
      setSelectedPoId("");
      setDeliveryNote("");
      setNotes("");
      setLineInputs({});
      qc.invalidateQueries({ queryKey: ["goods-receipts"] });
      qc.invalidateQueries({ queryKey: ["purchasing-orders"] });
    },
    onError: (e) => toast.error(e instanceof ApiError ? e.message : "Failed to post goods receipt"),
  });

  const receipts = receiptsData?.results ?? [];

  return (
    <div className="space-y-6">
      <PageHeader
        title="Goods Receiving (GRN)"
        subtitle="Receive incoming supplier shipments against approved/sent Purchase Orders and atomically increment warehouse stock."
      />

      {can("purchase.receive") && (
        <Card title="Receive Shipment Against Purchase Order">
          <div className="space-y-4">
            <div className="grid gap-3 sm:grid-cols-3">
              <div>
                <label className="mb-1 block text-xs font-medium text-slate-700">Purchase Order *</label>
                <select
                  value={selectedPoId}
                  onChange={(e) => handleSelectPo(e.target.value)}
                  className="w-full rounded-md border border-slate-300 px-3 py-1.5 text-sm"
                >
                  <option value="">Select receivable PO...</option>
                  {receivableOrders.map((po) => (
                    <option key={po.id} value={po.id}>
                      {po.po_number} — {po.supplier_name} ({po.status})
                    </option>
                  ))}
                </select>
              </div>
              <div>
                <label className="mb-1 block text-xs font-medium text-slate-700">Destination Warehouse *</label>
                <select
                  value={warehouseId}
                  onChange={(e) => setWarehouseId(e.target.value)}
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
                <label className="mb-1 block text-xs font-medium text-slate-700">Supplier Delivery Note</label>
                <input
                  type="text"
                  value={deliveryNote}
                  onChange={(e) => setDeliveryNote(e.target.value)}
                  placeholder="Packing slip / AWB #"
                  className="w-full rounded-md border border-slate-300 px-3 py-1.5 text-sm"
                />
              </div>
            </div>

            {selectedPo && (
              <div className="space-y-3 border-t border-slate-100 pt-3">
                <div className="text-xs font-semibold uppercase text-slate-600">
                  Outstanding Lines on {selectedPo.po_number}
                </div>
                {selectedPo.items
                  .filter((i) => Number(i.quantity_outstanding) > 0)
                  .map((item) => {
                    const st = lineInputs[item.id] ?? { qty: "0", location: "", lot_batch: "" };
                    return (
                      <div
                        key={item.id}
                        className="grid gap-3 rounded-md border border-slate-200 bg-slate-50/60 p-3 sm:grid-cols-4"
                      >
                        <div>
                          <div className="font-mono text-xs font-bold text-blue-700">
                            {item.component_internal_part_number}
                          </div>
                          <div className="text-xs text-slate-600">{item.mpn_snapshot || item.component_name}</div>
                          <div className="mt-1 font-mono text-[11px] text-slate-500">
                            Ordered: {Number(item.quantity_ordered)} · Outstanding:{" "}
                            {Number(item.quantity_outstanding)}
                          </div>
                        </div>
                        <div>
                          <label className="mb-1 block text-xs font-medium text-slate-700">Qty Received *</label>
                          <input
                            type="number"
                            min="0"
                            max={Number(item.quantity_outstanding)}
                            value={st.qty}
                            onChange={(e) =>
                              setLineInputs({
                                ...lineInputs,
                                [item.id]: { ...st, qty: e.target.value },
                              })
                            }
                            className="w-full rounded-md border border-slate-300 bg-white px-2.5 py-1.5 font-mono text-sm"
                          />
                        </div>
                        <div>
                          <label className="mb-1 block text-xs font-medium text-slate-700">Bin Location</label>
                          <select
                            value={st.location}
                            onChange={(e) =>
                              setLineInputs({
                                ...lineInputs,
                                [item.id]: { ...st, location: e.target.value },
                              })
                            }
                            className="w-full rounded-md border border-slate-300 bg-white px-2.5 py-1.5 text-sm"
                          >
                            <option value="">Unassigned</option>
                            {(locationsData?.results ?? []).map((loc) => (
                              <option key={loc.id} value={loc.id}>
                                {loc.code} — {loc.name}
                              </option>
                            ))}
                          </select>
                        </div>
                        <div>
                          <label className="mb-1 block text-xs font-medium text-slate-700">Lot / Batch</label>
                          <input
                            type="text"
                            value={st.lot_batch}
                            onChange={(e) =>
                              setLineInputs({
                                ...lineInputs,
                                [item.id]: { ...st, lot_batch: e.target.value },
                              })
                            }
                            placeholder="LOT-2026"
                            className="w-full rounded-md border border-slate-300 bg-white px-2.5 py-1.5 font-mono text-sm"
                          />
                        </div>
                      </div>
                    );
                  })}

                <div className="flex justify-end pt-2">
                  <Button
                    loading={postReceiptMut.isPending}
                    disabled={
                      !warehouseId ||
                      Object.values(lineInputs).every((v) => !v.qty || Number(v.qty) <= 0)
                    }
                    onClick={() => postReceiptMut.mutate()}
                  >
                    <PackageCheck className="h-4 w-4" /> Post Goods Receipt (GRN)
                  </Button>
                </div>
              </div>
            )}
          </div>
        </Card>
      )}

      {isLoading ? (
        <div className="flex justify-center py-12">
          <Spinner />
        </div>
      ) : error ? (
        <ErrorState message="Failed to load goods receipts." />
      ) : receipts.length === 0 ? (
        <EmptyState
          title="No goods receipts recorded"
          description="Posted goods receipts appear here with their linked purchase order and immutable stock transactions."
        />
      ) : (
        <Card title={`Posted Goods Receipts (${receipts.length})`}>
          <div className="overflow-x-auto">
            <table className="w-full text-left text-sm">
              <thead className="border-b border-slate-200 text-xs uppercase text-slate-500">
                <tr>
                  <th className="py-2 pr-3">GRN #</th>
                  <th className="py-2 pr-3">Purchase Order</th>
                  <th className="py-2 pr-3">Supplier</th>
                  <th className="py-2 pr-3">Warehouse</th>
                  <th className="py-2 pr-3">Delivery Note</th>
                  <th className="py-2 pr-3">Items</th>
                  <th className="py-2 pr-3">Received By</th>
                  <th className="py-2 pr-3">Received At</th>
                  <th className="py-2 text-right">Status</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {receipts.map((grn) => (
                  <tr key={grn.id}>
                    <td className="py-2.5 pr-3 font-mono text-xs font-semibold text-slate-900">
                      {grn.receipt_number}
                    </td>
                    <td className="py-2.5 pr-3 font-mono text-xs font-semibold">
                      <Link href={`/purchasing/orders/${grn.purchase_order}`} className="text-blue-700 hover:underline">
                        {grn.po_number}
                      </Link>
                    </td>
                    <td className="py-2.5 pr-3 text-xs font-medium">{grn.supplier_name}</td>
                    <td className="py-2.5 pr-3 font-mono text-xs">{grn.warehouse_code}</td>
                    <td className="py-2.5 pr-3 text-xs text-slate-600">{grn.supplier_delivery_note || "—"}</td>
                    <td className="py-2.5 pr-3 font-mono text-xs">{grn.items.length}</td>
                    <td className="py-2.5 pr-3 text-xs">{grn.received_by_name || "—"}</td>
                    <td className="py-2.5 pr-3 text-xs text-slate-500">
                      {grn.received_at ? formatDateTime(grn.received_at) : "—"}
                    </td>
                    <td className="py-2.5 text-right">
                      <Badge tone="green">{grn.status}</Badge>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Card>
      )}
    </div>
  );
}
