"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Plus, Search, Star } from "lucide-react";
import Link from "next/link";
import { useState } from "react";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import { Badge, Card, EmptyState, ErrorState, Modal, PageHeader, Spinner } from "@/components/ui/primitives";
import { api, ApiError, type Paginated } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import type { Supplier, SupplierStatus } from "@/lib/types";

const STATUS_TONE: Record<SupplierStatus, "green" | "amber" | "slate"> = {
  ACTIVE: "green",
  ON_HOLD: "amber",
  INACTIVE: "slate",
};

export default function SuppliersPage() {
  const { can } = useAuth();
  const qc = useQueryClient();
  const [search, setSearch] = useState("");
  const [statusFilter, setStatusFilter] = useState("");
  const [openCreate, setOpenCreate] = useState(false);

  const [form, setForm] = useState({
    code: "",
    name: "",
    legal_name: "",
    country: "",
    currency: "USD",
    payment_terms: "Net 30",
    lead_time_days: "7",
    rating: "5",
    email: "",
    phone: "",
    website: "",
    address: "",
    notes: "",
  });

  const { data, isLoading, error } = useQuery<Paginated<Supplier>>({
    queryKey: ["suppliers", search, statusFilter],
    queryFn: () =>
      api<Paginated<Supplier>>("suppliers", {
        query: {
          search: search || undefined,
          status: statusFilter || undefined,
          page_size: 100,
        },
      }),
  });

  const createMut = useMutation({
    mutationFn: () =>
      api<Supplier>("suppliers", {
        method: "POST",
        body: {
          ...form,
          code: form.code.trim() || undefined,
          lead_time_days: form.lead_time_days ? Number(form.lead_time_days) : null,
          rating: form.rating ? Number(form.rating) : null,
        },
      }),
    onSuccess: (created) => {
      toast.success(`Supplier ${created.name} (${created.code}) created`);
      setOpenCreate(false);
      setForm({
        code: "",
        name: "",
        legal_name: "",
        country: "",
        currency: "USD",
        payment_terms: "Net 30",
        lead_time_days: "7",
        rating: "5",
        email: "",
        phone: "",
        website: "",
        address: "",
        notes: "",
      });
      qc.invalidateQueries({ queryKey: ["suppliers"] });
    },
    onError: (e) => toast.error(e instanceof ApiError ? e.message : "Failed to create supplier"),
  });

  const suppliers = data?.results ?? [];

  return (
    <div className="space-y-6">
      <PageHeader
        title="Suppliers"
        subtitle="Approved component vendors, distributor accounts, lead times, and commercial terms."
        actions={
          can("supplier.create") && (
            <Button onClick={() => setOpenCreate(true)}>
              <Plus className="h-4 w-4" /> New Supplier
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
              placeholder="Search by supplier code, name, country, email..."
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              className="w-full rounded-md border border-slate-300 py-1.5 pl-9 pr-3 text-sm focus:border-blue-600 focus:outline-none"
            />
          </div>
          <select
            value={statusFilter}
            onChange={(e) => setStatusFilter(e.target.value)}
            className="rounded-md border border-slate-300 px-3 py-1.5 text-sm"
          >
            <option value="">All Statuses</option>
            <option value="ACTIVE">Active</option>
            <option value="ON_HOLD">On Hold</option>
            <option value="INACTIVE">Inactive</option>
          </select>
        </div>
      </Card>

      {isLoading ? (
        <div className="flex justify-center py-12">
          <Spinner />
        </div>
      ) : error ? (
        <ErrorState message="Failed to load suppliers." />
      ) : suppliers.length === 0 ? (
        <EmptyState
          title="No suppliers found"
          description="Add your component distributors and manufacturers to track supplier part numbers, MOQs, price breaks, and purchase orders."
          action={
            can("supplier.create") && (
              <Button onClick={() => setOpenCreate(true)}>
                <Plus className="h-4 w-4" /> Add Supplier
              </Button>
            )
          }
        />
      ) : (
        <div className="overflow-x-auto rounded-lg border border-slate-200 bg-white shadow-sm">
          <table className="w-full text-left text-sm">
            <thead className="border-b border-slate-200 bg-slate-50 text-xs font-semibold uppercase text-slate-600">
              <tr>
                <th className="px-4 py-3">Code</th>
                <th className="px-4 py-3">Supplier Name</th>
                <th className="px-4 py-3">Country</th>
                <th className="px-4 py-3">Currency</th>
                <th className="px-4 py-3">Payment Terms</th>
                <th className="px-4 py-3">Lead Time</th>
                <th className="px-4 py-3">Rating</th>
                <th className="px-4 py-3">Parts</th>
                <th className="px-4 py-3">POs</th>
                <th className="px-4 py-3">Status</th>
                <th className="px-4 py-3 text-right">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {suppliers.map((s) => (
                <tr key={s.id} className="hover:bg-slate-50">
                  <td className="px-4 py-3 font-mono text-xs font-semibold text-blue-700">
                    <Link href={`/suppliers/${s.id}`} className="hover:underline">
                      {s.code}
                    </Link>
                  </td>
                  <td className="px-4 py-3 font-medium text-slate-900">
                    <Link href={`/suppliers/${s.id}`} className="hover:text-blue-700 hover:underline">
                      {s.name}
                    </Link>
                    {s.email && <div className="text-xs text-slate-500">{s.email}</div>}
                  </td>
                  <td className="px-4 py-3 text-slate-600">{s.country || "—"}</td>
                  <td className="px-4 py-3 font-mono text-xs">{s.currency}</td>
                  <td className="px-4 py-3 text-slate-600">{s.payment_terms || "—"}</td>
                  <td className="px-4 py-3 text-slate-600">
                    {s.lead_time_days != null ? `${s.lead_time_days}d` : "—"}
                  </td>
                  <td className="px-4 py-3">
                    {s.rating ? (
                      <span className="inline-flex items-center gap-1 text-amber-600">
                        <Star className="h-3.5 w-3.5 fill-amber-400" /> {s.rating}/5
                      </span>
                    ) : (
                      "—"
                    )}
                  </td>
                  <td className="px-4 py-3 font-mono text-xs">{s.part_count}</td>
                  <td className="px-4 py-3 font-mono text-xs">{s.purchase_order_count}</td>
                  <td className="px-4 py-3">
                    <Badge tone={STATUS_TONE[s.status]}>{s.status}</Badge>
                  </td>
                  <td className="px-4 py-3 text-right">
                    <Link href={`/suppliers/${s.id}`} className="text-xs font-semibold text-blue-700 hover:underline">
                      View Details
                    </Link>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      <Modal
        open={openCreate}
        title="Create Supplier"
        onClose={() => setOpenCreate(false)}
        footer={
          <>
            <Button variant="secondary" onClick={() => setOpenCreate(false)}>
              Cancel
            </Button>
            <Button
              loading={createMut.isPending}
              disabled={!form.name.trim()}
              onClick={() => createMut.mutate()}
            >
              Create Supplier
            </Button>
          </>
        }
      >
        <div className="grid gap-3 sm:grid-cols-2">
          <div className="sm:col-span-2">
            <label className="mb-1 block text-xs font-medium text-slate-700">Supplier Name *</label>
            <input
              type="text"
              value={form.name}
              onChange={(e) => setForm({ ...form, name: e.target.value })}
              placeholder="e.g. DigiKey Electronics"
              className="w-full rounded-md border border-slate-300 px-3 py-1.5 text-sm"
            />
          </div>
          <div>
            <label className="mb-1 block text-xs font-medium text-slate-700">Code (blank = auto SUP-NNNN)</label>
            <input
              type="text"
              value={form.code}
              onChange={(e) => setForm({ ...form, code: e.target.value })}
              placeholder="SUP-0001"
              className="w-full rounded-md border border-slate-300 px-3 py-1.5 text-sm font-mono"
            />
          </div>
          <div>
            <label className="mb-1 block text-xs font-medium text-slate-700">Country</label>
            <input
              type="text"
              value={form.country}
              onChange={(e) => setForm({ ...form, country: e.target.value })}
              placeholder="United States"
              className="w-full rounded-md border border-slate-300 px-3 py-1.5 text-sm"
            />
          </div>
          <div>
            <label className="mb-1 block text-xs font-medium text-slate-700">Currency (ISO 3-letter)</label>
            <input
              type="text"
              maxLength={3}
              value={form.currency}
              onChange={(e) => setForm({ ...form, currency: e.target.value.toUpperCase() })}
              className="w-full rounded-md border border-slate-300 px-3 py-1.5 text-sm font-mono uppercase"
            />
          </div>
          <div>
            <label className="mb-1 block text-xs font-medium text-slate-700">Payment Terms</label>
            <input
              type="text"
              value={form.payment_terms}
              onChange={(e) => setForm({ ...form, payment_terms: e.target.value })}
              placeholder="Net 30"
              className="w-full rounded-md border border-slate-300 px-3 py-1.5 text-sm"
            />
          </div>
          <div>
            <label className="mb-1 block text-xs font-medium text-slate-700">Default Lead Time (days)</label>
            <input
              type="number"
              min={0}
              value={form.lead_time_days}
              onChange={(e) => setForm({ ...form, lead_time_days: e.target.value })}
              className="w-full rounded-md border border-slate-300 px-3 py-1.5 text-sm"
            />
          </div>
          <div>
            <label className="mb-1 block text-xs font-medium text-slate-700">Rating (1–5)</label>
            <select
              value={form.rating}
              onChange={(e) => setForm({ ...form, rating: e.target.value })}
              className="w-full rounded-md border border-slate-300 px-3 py-1.5 text-sm"
            >
              <option value="">Unrated</option>
              <option value="5">5 - Preferred</option>
              <option value="4">4 - Good</option>
              <option value="3">3 - Acceptable</option>
              <option value="2">2 - Conditional</option>
              <option value="1">1 - Restricted</option>
            </select>
          </div>
          <div>
            <label className="mb-1 block text-xs font-medium text-slate-700">Email</label>
            <input
              type="email"
              value={form.email}
              onChange={(e) => setForm({ ...form, email: e.target.value })}
              placeholder="orders@supplier.example"
              className="w-full rounded-md border border-slate-300 px-3 py-1.5 text-sm"
            />
          </div>
          <div>
            <label className="mb-1 block text-xs font-medium text-slate-700">Phone</label>
            <input
              type="text"
              value={form.phone}
              onChange={(e) => setForm({ ...form, phone: e.target.value })}
              className="w-full rounded-md border border-slate-300 px-3 py-1.5 text-sm"
            />
          </div>
          <div className="sm:col-span-2">
            <label className="mb-1 block text-xs font-medium text-slate-700">Website</label>
            <input
              type="url"
              value={form.website}
              onChange={(e) => setForm({ ...form, website: e.target.value })}
              placeholder="https://www.digikey.com"
              className="w-full rounded-md border border-slate-300 px-3 py-1.5 text-sm"
            />
          </div>
          <div className="sm:col-span-2">
            <label className="mb-1 block text-xs font-medium text-slate-700">Notes</label>
            <textarea
              rows={2}
              value={form.notes}
              onChange={(e) => setForm({ ...form, notes: e.target.value })}
              className="w-full rounded-md border border-slate-300 px-3 py-1.5 text-sm"
            />
          </div>
        </div>
      </Modal>
    </div>
  );
}
