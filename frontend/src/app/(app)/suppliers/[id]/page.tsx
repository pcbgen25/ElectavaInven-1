"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ExternalLink, History, Pencil, Plus, Trash2 } from "lucide-react";
import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { useState } from "react";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import { Badge, Card, DescriptionList, ErrorState, Modal, PageHeader, Spinner } from "@/components/ui/primitives";
import { api, ApiError, type Paginated } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import type {
  ComponentListItem,
  Supplier,
  SupplierPart,
  SupplierPriceHistory,
  SupplierStatus,
} from "@/lib/types";
import { formatDateTime } from "@/lib/utils";

const STATUS_TONE: Record<SupplierStatus, "green" | "amber" | "slate"> = {
  ACTIVE: "green",
  ON_HOLD: "amber",
  INACTIVE: "slate",
};

export default function SupplierDetailPage() {
  const { id } = useParams<{ id: string }>();
  const router = useRouter();
  const qc = useQueryClient();
  const { can } = useAuth();

  const [openEdit, setOpenEdit] = useState(false);
  const [openContact, setOpenContact] = useState(false);
  const [openAddPart, setOpenAddPart] = useState(false);
  const [historyPart, setHistoryPart] = useState<SupplierPart | null>(null);

  const { data: supplier, isLoading } = useQuery<Supplier>({
    queryKey: ["supplier", id],
    queryFn: () => api<Supplier>(`suppliers/${id}`),
  });

  const { data: partsData } = useQuery<Paginated<SupplierPart>>({
    queryKey: ["supplier-parts", { supplier: id }],
    queryFn: () => api<Paginated<SupplierPart>>("supplier-parts", { query: { supplier: id, page_size: 100 } }),
  });

  const { data: componentsData } = useQuery<Paginated<ComponentListItem>>({
    queryKey: ["components", "dropdown"],
    queryFn: () => api<Paginated<ComponentListItem>>("components", { query: { page_size: 100 } }),
    enabled: openAddPart,
  });

  const { data: priceHistory } = useQuery<SupplierPriceHistory[]>({
    queryKey: ["supplier-part-history", historyPart?.id],
    queryFn: () => api<SupplierPriceHistory[]>(`supplier-parts/${historyPart!.id}/price-history`),
    enabled: !!historyPart,
  });

  const [editForm, setEditForm] = useState({
    name: "",
    status: "ACTIVE" as SupplierStatus,
    country: "",
    currency: "USD",
    payment_terms: "",
    lead_time_days: "",
    rating: "",
    email: "",
    phone: "",
    website: "",
    notes: "",
  });

  const [contactForm, setContactForm] = useState({
    name: "",
    role: "",
    email: "",
    phone: "",
    is_primary: true,
  });

  const [partForm, setPartForm] = useState({
    component: "",
    supplier_part_number: "",
    packaging: "Tape & Reel",
    unit_price: "0.100000",
    moq: "1",
    order_multiple: "1",
    lead_time_days: "7",
    is_preferred: true,
    break_qty_1: "100",
    break_price_1: "",
  });

  const updateSupplierMut = useMutation({
    mutationFn: () =>
      api(`suppliers/${id}`, {
        method: "PATCH",
        body: {
          ...editForm,
          lead_time_days: editForm.lead_time_days ? Number(editForm.lead_time_days) : null,
          rating: editForm.rating ? Number(editForm.rating) : null,
        },
      }),
    onSuccess: () => {
      toast.success("Supplier updated");
      setOpenEdit(false);
      qc.invalidateQueries({ queryKey: ["supplier", id] });
      qc.invalidateQueries({ queryKey: ["suppliers"] });
    },
    onError: (e) => toast.error(e instanceof ApiError ? e.message : "Failed to update supplier"),
  });

  const deleteSupplierMut = useMutation({
    mutationFn: () => api(`suppliers/${id}`, { method: "DELETE" }),
    onSuccess: () => {
      toast.success("Supplier deleted");
      router.push("/suppliers");
    },
    onError: (e) => toast.error(e instanceof ApiError ? e.message : "Cannot delete supplier"),
  });

  const addContactMut = useMutation({
    mutationFn: () => api(`suppliers/${id}/contacts`, { method: "POST", body: contactForm }),
    onSuccess: () => {
      toast.success("Contact added");
      setOpenContact(false);
      setContactForm({ name: "", role: "", email: "", phone: "", is_primary: false });
      qc.invalidateQueries({ queryKey: ["supplier", id] });
    },
    onError: (e) => toast.error(e instanceof ApiError ? e.message : "Failed to add contact"),
  });

  const removeContactMut = useMutation({
    mutationFn: (contactId: number) => api(`suppliers/${id}/contacts/${contactId}`, { method: "DELETE" }),
    onSuccess: () => {
      toast.success("Contact removed");
      qc.invalidateQueries({ queryKey: ["supplier", id] });
    },
  });

  const addPartMut = useMutation({
    mutationFn: () => {
      const price_breaks =
        partForm.break_qty_1 && partForm.break_price_1
          ? [
              {
                min_quantity: partForm.break_qty_1,
                unit_price: partForm.break_price_1,
                currency: supplier?.currency || "USD",
              },
            ]
          : [];
      return api("supplier-parts", {
        method: "POST",
        body: {
          supplier: Number(id),
          component: Number(partForm.component),
          supplier_part_number: partForm.supplier_part_number,
          packaging: partForm.packaging,
          currency: supplier?.currency || "USD",
          unit_price: partForm.unit_price,
          moq: partForm.moq,
          order_multiple: partForm.order_multiple,
          lead_time_days: partForm.lead_time_days ? Number(partForm.lead_time_days) : null,
          is_preferred: partForm.is_preferred,
          price_breaks,
        },
      });
    },
    onSuccess: () => {
      toast.success("Supplier part added");
      setOpenAddPart(false);
      qc.invalidateQueries({ queryKey: ["supplier-parts", { supplier: id }] });
      qc.invalidateQueries({ queryKey: ["supplier", id] });
    },
    onError: (e) => toast.error(e instanceof ApiError ? e.message : "Failed to add supplier part"),
  });

  if (isLoading) {
    return (
      <div className="flex justify-center py-12">
        <Spinner />
      </div>
    );
  }
  if (!supplier) return <ErrorState message="Supplier not found." />;

  const parts = partsData?.results ?? [];

  return (
    <div className="space-y-6">
      <PageHeader
        title={
          <span className="flex items-center gap-2.5">
            <span className="pn">{supplier.code}</span>
            <span>{supplier.name}</span>
            <Badge tone={STATUS_TONE[supplier.status]}>{supplier.status}</Badge>
          </span>
        }
        subtitle={
          <>
            <Link href="/suppliers" className="text-blue-700 hover:underline">
              Suppliers
            </Link>{" "}
            / {supplier.country || "Global"} · Currency: {supplier.currency}
          </>
        }
        actions={
          <div className="flex items-center gap-2">
            {can("supplier.edit") && (
              <Button
                variant="secondary"
                onClick={() => {
                  setEditForm({
                    name: supplier.name,
                    status: supplier.status,
                    country: supplier.country || "",
                    currency: supplier.currency || "USD",
                    payment_terms: supplier.payment_terms || "",
                    lead_time_days: supplier.lead_time_days != null ? String(supplier.lead_time_days) : "",
                    rating: supplier.rating != null ? String(supplier.rating) : "",
                    email: supplier.email || "",
                    phone: supplier.phone || "",
                    website: supplier.website || "",
                    notes: supplier.notes || "",
                  });
                  setOpenEdit(true);
                }}
              >
                <Pencil className="h-4 w-4" /> Edit
              </Button>
            )}
            {can("supplier.delete") && (
              <Button
                variant="danger"
                loading={deleteSupplierMut.isPending}
                onClick={() => {
                  if (confirm(`Delete supplier ${supplier.name}?`)) deleteSupplierMut.mutate();
                }}
              >
                <Trash2 className="h-4 w-4" /> Delete
              </Button>
            )}
          </div>
        }
      />

      <div className="grid gap-6 lg:grid-cols-3">
        <div className="space-y-6 lg:col-span-2">
          <Card title="Commercial Profile">
            <DescriptionList
              items={[
                { label: "Supplier Code", value: <span className="pn">{supplier.code}</span> },
                { label: "Name", value: supplier.name },
                { label: "Country", value: supplier.country || "—" },
                { label: "Default Currency", value: supplier.currency },
                { label: "Payment Terms", value: supplier.payment_terms || "—" },
                {
                  label: "Default Lead Time",
                  value: supplier.lead_time_days != null ? `${supplier.lead_time_days} days` : "—",
                },
                { label: "Rating", value: supplier.rating ? `${supplier.rating} / 5` : "—" },
                { label: "Email", value: supplier.email || "—" },
                { label: "Phone", value: supplier.phone || "—" },
                {
                  label: "Website",
                  value: supplier.website && (
                    <a
                      href={supplier.website}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="inline-flex items-center gap-1 text-blue-700 hover:underline"
                    >
                      {supplier.website} <ExternalLink className="h-3 w-3" />
                    </a>
                  ),
                },
              ]}
            />
            {supplier.notes && (
              <div className="mt-4 rounded-md bg-slate-50 p-3 text-sm text-slate-700">{supplier.notes}</div>
            )}
          </Card>

          <Card
            title={`Supplier Parts Catalog (${parts.length})`}
            actions={
              can("supplier.create") && (
                <Button onClick={() => setOpenAddPart(true)}>
                  <Plus className="h-4 w-4" /> Add Supplier Part
                </Button>
              )
            }
          >
            {parts.length === 0 ? (
              <p className="text-sm text-slate-500">No supplier part numbers linked to this supplier yet.</p>
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full text-left text-sm">
                  <thead className="border-b border-slate-200 text-xs uppercase text-slate-500">
                    <tr>
                      <th className="py-2 pr-3">Supplier PN</th>
                      <th className="py-2 pr-3">Component</th>
                      <th className="py-2 pr-3">Unit Price</th>
                      <th className="py-2 pr-3">MOQ / Mult</th>
                      <th className="py-2 pr-3">Price Breaks</th>
                      <th className="py-2 text-right">History</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-100">
                    {parts.map((p) => (
                      <tr key={p.id}>
                        <td className="py-2.5 pr-3 font-mono text-xs font-semibold">
                          {p.supplier_part_number}
                          {p.is_preferred && (
                            <span className="ml-2">
                              <Badge tone="blue">Preferred</Badge>
                            </span>
                          )}
                        </td>
                        <td className="py-2.5 pr-3">
                          <Link
                            href={`/components/${p.component}`}
                            className="font-mono text-xs text-blue-700 hover:underline"
                          >
                            {p.component_internal_part_number}
                          </Link>
                          <div className="text-xs text-slate-500">{p.component_mpn || p.component_name}</div>
                        </td>
                        <td className="py-2.5 pr-3 font-mono text-xs">
                          {Number(p.unit_price).toFixed(4)} {p.currency}
                        </td>
                        <td className="py-2.5 pr-3 font-mono text-xs">
                          {Number(p.moq)} / {Number(p.order_multiple)}
                        </td>
                        <td className="py-2.5 pr-3 text-xs text-slate-600">
                          {p.price_breaks.length === 0
                            ? "Base only"
                            : p.price_breaks
                                .map((b) => `${Number(b.min_quantity)}+: ${Number(b.unit_price).toFixed(4)}`)
                                .join(", ")}
                        </td>
                        <td className="py-2.5 text-right">
                          <button
                            type="button"
                            onClick={() => setHistoryPart(p)}
                            className="inline-flex items-center gap-1 text-xs font-medium text-blue-700 hover:underline"
                          >
                            <History className="h-3.5 w-3.5" /> History
                          </button>
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
          <Card
            title="Supplier Contacts"
            actions={
              can("supplier.edit") && (
                <Button variant="secondary" onClick={() => setOpenContact(true)}>
                  <Plus className="h-3.5 w-3.5" /> Add
                </Button>
              )
            }
          >
            {supplier.contacts.length === 0 ? (
              <p className="text-sm text-slate-500">No contacts recorded.</p>
            ) : (
              <ul className="divide-y divide-slate-100 text-sm">
                {supplier.contacts.map((c) => (
                  <li key={c.id} className="flex items-start justify-between gap-2 py-2.5">
                    <div>
                      <div className="font-medium text-slate-900">
                        {c.name}{" "}
                        {c.is_primary && (
                          <span className="ml-1">
                            <Badge tone="green">Primary</Badge>
                          </span>
                        )}
                      </div>
                      {c.role && <div className="text-xs text-slate-500">{c.role}</div>}
                      {c.email && <div className="text-xs text-blue-700">{c.email}</div>}
                      {c.phone && <div className="text-xs text-slate-600">{c.phone}</div>}
                    </div>
                    {can("supplier.edit") && (
                      <button
                        type="button"
                        onClick={() => removeContactMut.mutate(c.id)}
                        className="text-xs text-red-600 hover:underline"
                      >
                        Remove
                      </button>
                    )}
                  </li>
                ))}
              </ul>
            )}
          </Card>
        </div>
      </div>

      {/* Edit Supplier Modal */}
      <Modal
        open={openEdit}
        title={`Edit ${supplier.name}`}
        onClose={() => setOpenEdit(false)}
        footer={
          <>
            <Button variant="secondary" onClick={() => setOpenEdit(false)}>
              Cancel
            </Button>
            <Button loading={updateSupplierMut.isPending} onClick={() => updateSupplierMut.mutate()}>
              Save Changes
            </Button>
          </>
        }
      >
        <div className="grid gap-3 sm:grid-cols-2">
          <div className="sm:col-span-2">
            <label className="mb-1 block text-xs font-medium text-slate-700">Name</label>
            <input
              type="text"
              value={editForm.name}
              onChange={(e) => setEditForm({ ...editForm, name: e.target.value })}
              className="w-full rounded-md border border-slate-300 px-3 py-1.5 text-sm"
            />
          </div>
          <div>
            <label className="mb-1 block text-xs font-medium text-slate-700">Status</label>
            <select
              value={editForm.status}
              onChange={(e) => setEditForm({ ...editForm, status: e.target.value as SupplierStatus })}
              className="w-full rounded-md border border-slate-300 px-3 py-1.5 text-sm"
            >
              <option value="ACTIVE">ACTIVE</option>
              <option value="ON_HOLD">ON_HOLD</option>
              <option value="INACTIVE">INACTIVE</option>
            </select>
          </div>
          <div>
            <label className="mb-1 block text-xs font-medium text-slate-700">Currency</label>
            <input
              type="text"
              maxLength={3}
              value={editForm.currency}
              onChange={(e) => setEditForm({ ...editForm, currency: e.target.value.toUpperCase() })}
              className="w-full rounded-md border border-slate-300 px-3 py-1.5 text-sm font-mono uppercase"
            />
          </div>
          <div>
            <label className="mb-1 block text-xs font-medium text-slate-700">Payment Terms</label>
            <input
              type="text"
              value={editForm.payment_terms}
              onChange={(e) => setEditForm({ ...editForm, payment_terms: e.target.value })}
              className="w-full rounded-md border border-slate-300 px-3 py-1.5 text-sm"
            />
          </div>
          <div>
            <label className="mb-1 block text-xs font-medium text-slate-700">Lead Time (days)</label>
            <input
              type="number"
              min={0}
              value={editForm.lead_time_days}
              onChange={(e) => setEditForm({ ...editForm, lead_time_days: e.target.value })}
              className="w-full rounded-md border border-slate-300 px-3 py-1.5 text-sm"
            />
          </div>
        </div>
      </Modal>

      {/* Add Contact Modal */}
      <Modal
        open={openContact}
        title="Add Supplier Contact"
        onClose={() => setOpenContact(false)}
        footer={
          <>
            <Button variant="secondary" onClick={() => setOpenContact(false)}>
              Cancel
            </Button>
            <Button
              loading={addContactMut.isPending}
              disabled={!contactForm.name.trim()}
              onClick={() => addContactMut.mutate()}
            >
              Add Contact
            </Button>
          </>
        }
      >
        <div className="space-y-3">
          <div>
            <label className="mb-1 block text-xs font-medium text-slate-700">Full Name *</label>
            <input
              type="text"
              value={contactForm.name}
              onChange={(e) => setContactForm({ ...contactForm, name: e.target.value })}
              className="w-full rounded-md border border-slate-300 px-3 py-1.5 text-sm"
            />
          </div>
          <div>
            <label className="mb-1 block text-xs font-medium text-slate-700">Role</label>
            <input
              type="text"
              value={contactForm.role}
              onChange={(e) => setContactForm({ ...contactForm, role: e.target.value })}
              placeholder="Account Manager"
              className="w-full rounded-md border border-slate-300 px-3 py-1.5 text-sm"
            />
          </div>
          <div>
            <label className="mb-1 block text-xs font-medium text-slate-700">Email</label>
            <input
              type="email"
              value={contactForm.email}
              onChange={(e) => setContactForm({ ...contactForm, email: e.target.value })}
              className="w-full rounded-md border border-slate-300 px-3 py-1.5 text-sm"
            />
          </div>
          <div>
            <label className="mb-1 block text-xs font-medium text-slate-700">Phone</label>
            <input
              type="text"
              value={contactForm.phone}
              onChange={(e) => setContactForm({ ...contactForm, phone: e.target.value })}
              className="w-full rounded-md border border-slate-300 px-3 py-1.5 text-sm"
            />
          </div>
          <label className="flex items-center gap-2 text-sm">
            <input
              type="checkbox"
              checked={contactForm.is_primary}
              onChange={(e) => setContactForm({ ...contactForm, is_primary: e.target.checked })}
            />
            Primary contact for this supplier
          </label>
        </div>
      </Modal>

      {/* Add SupplierPart Modal */}
      <Modal
        open={openAddPart}
        title="Add Supplier Part & Pricing"
        onClose={() => setOpenAddPart(false)}
        footer={
          <>
            <Button variant="secondary" onClick={() => setOpenAddPart(false)}>
              Cancel
            </Button>
            <Button
              loading={addPartMut.isPending}
              disabled={!partForm.component || !partForm.supplier_part_number.trim()}
              onClick={() => addPartMut.mutate()}
            >
              Add Supplier Part
            </Button>
          </>
        }
      >
        <div className="grid gap-3 sm:grid-cols-2">
          <div className="sm:col-span-2">
            <label className="mb-1 block text-xs font-medium text-slate-700">Internal Component *</label>
            <select
              value={partForm.component}
              onChange={(e) => setPartForm({ ...partForm, component: e.target.value })}
              className="w-full rounded-md border border-slate-300 px-3 py-1.5 text-sm"
            >
              <option value="">Select component...</option>
              {(componentsData?.results ?? []).map((c) => (
                <option key={c.id} value={c.id}>
                  {c.internal_part_number} — {c.mpn || c.name}
                </option>
              ))}
            </select>
          </div>
          <div>
            <label className="mb-1 block text-xs font-medium text-slate-700">Supplier Part Number (SPN) *</label>
            <input
              type="text"
              value={partForm.supplier_part_number}
              onChange={(e) => setPartForm({ ...partForm, supplier_part_number: e.target.value })}
              placeholder="e.g. 296-1234-1-ND"
              className="w-full rounded-md border border-slate-300 px-3 py-1.5 text-sm font-mono"
            />
          </div>
          <div>
            <label className="mb-1 block text-xs font-medium text-slate-700">Packaging</label>
            <input
              type="text"
              value={partForm.packaging}
              onChange={(e) => setPartForm({ ...partForm, packaging: e.target.value })}
              placeholder="Tape & Reel"
              className="w-full rounded-md border border-slate-300 px-3 py-1.5 text-sm"
            />
          </div>
          <div>
            <label className="mb-1 block text-xs font-medium text-slate-700">
              Base Unit Price ({supplier.currency}) *
            </label>
            <input
              type="number"
              step="0.0001"
              min="0"
              value={partForm.unit_price}
              onChange={(e) => setPartForm({ ...partForm, unit_price: e.target.value })}
              className="w-full rounded-md border border-slate-300 px-3 py-1.5 text-sm font-mono"
            />
          </div>
          <div>
            <label className="mb-1 block text-xs font-medium text-slate-700">Lead Time (days)</label>
            <input
              type="number"
              min="0"
              value={partForm.lead_time_days}
              onChange={(e) => setPartForm({ ...partForm, lead_time_days: e.target.value })}
              className="w-full rounded-md border border-slate-300 px-3 py-1.5 text-sm"
            />
          </div>
          <div>
            <label className="mb-1 block text-xs font-medium text-slate-700">MOQ</label>
            <input
              type="number"
              min="1"
              value={partForm.moq}
              onChange={(e) => setPartForm({ ...partForm, moq: e.target.value })}
              className="w-full rounded-md border border-slate-300 px-3 py-1.5 text-sm font-mono"
            />
          </div>
          <div>
            <label className="mb-1 block text-xs font-medium text-slate-700">Order Multiple</label>
            <input
              type="number"
              min="1"
              value={partForm.order_multiple}
              onChange={(e) => setPartForm({ ...partForm, order_multiple: e.target.value })}
              className="w-full rounded-md border border-slate-300 px-3 py-1.5 text-sm font-mono"
            />
          </div>
          <div>
            <label className="mb-1 block text-xs font-medium text-slate-700">Quantity Break (Optional Qty)</label>
            <input
              type="number"
              min="1"
              value={partForm.break_qty_1}
              onChange={(e) => setPartForm({ ...partForm, break_qty_1: e.target.value })}
              placeholder="100"
              className="w-full rounded-md border border-slate-300 px-3 py-1.5 text-sm font-mono"
            />
          </div>
          <div>
            <label className="mb-1 block text-xs font-medium text-slate-700">Quantity Break Unit Price</label>
            <input
              type="number"
              step="0.0001"
              min="0"
              value={partForm.break_price_1}
              onChange={(e) => setPartForm({ ...partForm, break_price_1: e.target.value })}
              placeholder="e.g. 0.0800"
              className="w-full rounded-md border border-slate-300 px-3 py-1.5 text-sm font-mono"
            />
          </div>
          <label className="flex items-center gap-2 text-sm sm:col-span-2">
            <input
              type="checkbox"
              checked={partForm.is_preferred}
              onChange={(e) => setPartForm({ ...partForm, is_preferred: e.target.checked })}
            />
            Preferred supplier part for this component
          </label>
        </div>
      </Modal>

      {/* Immutable Price History Modal */}
      <Modal
        open={!!historyPart}
        title={`Immutable Price History — ${historyPart?.supplier_part_number ?? ""}`}
        onClose={() => setHistoryPart(null)}
        footer={
          <Button variant="secondary" onClick={() => setHistoryPart(null)}>
            Close
          </Button>
        }
      >
        {!priceHistory || priceHistory.length === 0 ? (
          <p className="text-sm text-slate-500">No price history records.</p>
        ) : (
          <table className="w-full text-left text-xs">
            <thead className="border-b border-slate-200 uppercase text-slate-500">
              <tr>
                <th className="py-2">Recorded At</th>
                <th className="py-2">Min Qty</th>
                <th className="py-2">Unit Price</th>
                <th className="py-2">Source</th>
                <th className="py-2">Reference</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {priceHistory.map((h) => (
                <tr key={h.id}>
                  <td className="py-2">{formatDateTime(h.recorded_at)}</td>
                  <td className="py-2 font-mono">{Number(h.min_quantity)}</td>
                  <td className="py-2 font-mono font-semibold">
                    {Number(h.unit_price).toFixed(4)} {h.currency}
                  </td>
                  <td className="py-2">
                    <Badge tone="slate">{h.source}</Badge>
                  </td>
                  <td className="py-2 text-slate-500">{h.reference || "—"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </Modal>
    </div>
  );
}
