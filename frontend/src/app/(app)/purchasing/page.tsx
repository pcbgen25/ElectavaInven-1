"use client";

import { useQuery } from "@tanstack/react-query";
import { ClipboardCheck, FileSpreadsheet, PackageCheck, ShoppingCart, Truck } from "lucide-react";
import Link from "next/link";

import { Button } from "@/components/ui/button";
import { Badge, Card, ErrorState, PageHeader, Spinner } from "@/components/ui/primitives";
import { api, type Paginated } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import type { PurchaseOrder, PurchaseRequest, PurchasingSummary } from "@/lib/types";
import { formatDateTime } from "@/lib/utils";

export default function PurchasingOverviewPage() {
  const { can } = useAuth();

  const { data: summary, isLoading, error } = useQuery<PurchasingSummary>({
    queryKey: ["purchasing-summary"],
    queryFn: () => api<PurchasingSummary>("purchasing/summary"),
  });

  const { data: recentPRs } = useQuery<Paginated<PurchaseRequest>>({
    queryKey: ["purchasing-requests", "recent"],
    queryFn: () => api<Paginated<PurchaseRequest>>("purchasing/requests", { query: { page_size: 6 } }),
  });

  const { data: recentPOs } = useQuery<Paginated<PurchaseOrder>>({
    queryKey: ["purchasing-orders", "recent"],
    queryFn: () => api<Paginated<PurchaseOrder>>("purchasing/orders", { query: { page_size: 6 } }),
  });

  if (isLoading) {
    return (
      <div className="flex justify-center py-12">
        <Spinner />
      </div>
    );
  }
  if (error || !summary) return <ErrorState message="Failed to load purchasing overview." />;

  return (
    <div className="space-y-6">
      <PageHeader
        title="Purchasing & Procurement"
        subtitle="End-to-end engineering requisitions, controlled purchase orders, and atomic goods receipts."
        actions={
          <div className="flex flex-wrap gap-2">
            {can("purchase.create") && (
              <Link href="/purchasing/requests">
                <Button variant="secondary">
                  <FileSpreadsheet className="h-4 w-4" /> Purchase Requests
                </Button>
              </Link>
            )}
            {can("purchase.order") && (
              <Link href="/purchasing/orders">
                <Button variant="secondary">
                  <ShoppingCart className="h-4 w-4" /> Purchase Orders
                </Button>
              </Link>
            )}
            {can("purchase.receive") && (
              <Link href="/purchasing/receiving">
                <Button>
                  <PackageCheck className="h-4 w-4" /> Receive Goods (GRN)
                </Button>
              </Link>
            )}
          </div>
        }
      />

      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <Card>
          <div className="flex items-center justify-between">
            <div>
              <div className="text-xs font-medium uppercase tracking-wide text-slate-500">Open Requests</div>
              <div className="mt-1 text-2xl font-bold text-slate-900">{summary.open_requests}</div>
              <div className="mt-1 text-xs text-amber-600">
                {summary.pending_approval_requests} awaiting approval
              </div>
            </div>
            <ClipboardCheck className="h-8 w-8 text-blue-600" />
          </div>
        </Card>

        <Card>
          <div className="flex items-center justify-between">
            <div>
              <div className="text-xs font-medium uppercase tracking-wide text-slate-500">Open Purchase Orders</div>
              <div className="mt-1 text-2xl font-bold text-slate-900">{summary.open_orders}</div>
              <div className="mt-1 text-xs text-slate-500">
                {summary.awaiting_delivery_orders} awaiting delivery
              </div>
            </div>
            <ShoppingCart className="h-8 w-8 text-emerald-600" />
          </div>
        </Card>

        <Card>
          <div className="flex items-center justify-between">
            <div>
              <div className="text-xs font-medium uppercase tracking-wide text-slate-500">Open PO Commitment</div>
              <div className="mt-1 font-mono text-2xl font-bold text-slate-900">
                ${Number(summary.open_po_commitment).toFixed(2)}
              </div>
              <div className="mt-1 text-xs text-slate-500">Converted at PO exchange rate</div>
            </div>
            <Truck className="h-8 w-8 text-indigo-600" />
          </div>
        </Card>

        <Card>
          <div className="flex items-center justify-between">
            <div>
              <div className="text-xs font-medium uppercase tracking-wide text-slate-500">Posted Goods Receipts</div>
              <div className="mt-1 text-2xl font-bold text-slate-900">{summary.posted_receipts}</div>
              <div className="mt-1 text-xs text-emerald-600">Atomically posted to inventory</div>
            </div>
            <PackageCheck className="h-8 w-8 text-teal-600" />
          </div>
        </Card>
      </div>

      <div className="grid gap-6 lg:grid-cols-2">
        <Card
          title="Recent Purchase Requests"
          actions={
            <Link href="/purchasing/requests" className="text-xs font-medium text-blue-700 hover:underline">
              View All
            </Link>
          }
        >
          {(recentPRs?.results ?? []).length === 0 ? (
            <p className="text-sm text-slate-500">No purchase requests yet.</p>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-left text-sm">
                <thead className="border-b border-slate-200 text-xs uppercase text-slate-500">
                  <tr>
                    <th className="py-2">PR #</th>
                    <th className="py-2">Title</th>
                    <th className="py-2">Priority</th>
                    <th className="py-2">Status</th>
                    <th className="py-2 text-right">Est. Total</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100">
                  {(recentPRs?.results ?? []).map((pr) => (
                    <tr key={pr.id}>
                      <td className="py-2 font-mono text-xs font-semibold">
                        <Link href={`/purchasing/requests/${pr.id}`} className="text-blue-700 hover:underline">
                          {pr.request_number}
                        </Link>
                      </td>
                      <td className="py-2 font-medium text-slate-900">{pr.title}</td>
                      <td className="py-2">
                        <Badge tone={pr.priority === "URGENT" || pr.priority === "HIGH" ? "red" : "slate"}>
                          {pr.priority}
                        </Badge>
                      </td>
                      <td className="py-2">
                        <Badge
                          tone={
                            pr.status === "APPROVED" || pr.status === "ORDERED"
                              ? "green"
                              : pr.status === "REJECTED" || pr.status === "CANCELLED"
                                ? "red"
                                : "amber"
                          }
                        >
                          {pr.status}
                        </Badge>
                      </td>
                      <td className="py-2 text-right font-mono text-xs">
                        ${Number(pr.estimated_total).toFixed(2)}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </Card>

        <Card
          title="Recent Purchase Orders"
          actions={
            <Link href="/purchasing/orders" className="text-xs font-medium text-blue-700 hover:underline">
              View All
            </Link>
          }
        >
          {(recentPOs?.results ?? []).length === 0 ? (
            <p className="text-sm text-slate-500">No purchase orders yet.</p>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-left text-sm">
                <thead className="border-b border-slate-200 text-xs uppercase text-slate-500">
                  <tr>
                    <th className="py-2">PO #</th>
                    <th className="py-2">Supplier</th>
                    <th className="py-2">Status</th>
                    <th className="py-2">Created</th>
                    <th className="py-2 text-right">Total</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100">
                  {(recentPOs?.results ?? []).map((po) => (
                    <tr key={po.id}>
                      <td className="py-2 font-mono text-xs font-semibold">
                        <Link href={`/purchasing/orders/${po.id}`} className="text-blue-700 hover:underline">
                          {po.po_number}
                        </Link>
                      </td>
                      <td className="py-2 font-medium text-slate-900">{po.supplier_name}</td>
                      <td className="py-2">
                        <Badge
                          tone={
                            po.status === "RECEIVED" || po.status === "CLOSED"
                              ? "green"
                              : po.status === "PARTIALLY_RECEIVED" || po.status === "SENT" || po.status === "APPROVED"
                                ? "blue"
                                : po.status === "CANCELLED"
                                  ? "red"
                                  : "amber"
                          }
                        >
                          {po.status}
                        </Badge>
                      </td>
                      <td className="py-2 text-xs text-slate-500">{formatDateTime(po.created_at)}</td>
                      <td className="py-2 text-right font-mono text-xs font-semibold">
                        {Number(po.total_amount).toFixed(2)} {po.currency}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </Card>
      </div>
    </div>
  );
}
