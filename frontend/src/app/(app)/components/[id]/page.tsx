"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ExternalLink, FileText, ImageIcon, Pencil, Trash2, Upload } from "lucide-react";
import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { useRef, useState } from "react";

import { Button } from "@/components/ui/button";
import { Badge, Card, DescriptionList, ErrorState, LifecycleBadge, Modal, PageHeader, Spinner } from "@/components/ui/primitives";
import { useToast } from "@/components/ui/toast";
import { ApiError, api, type Paginated } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { ALIAS_TYPES, STATUS_LABELS, type AuditEntry, type ComponentDetail, type SupplierOfferComparison } from "@/lib/types";
import { formatDateTime, formatRelative, triState } from "@/lib/utils";

const MAX_IMAGE_MB = 5;
const MAX_DATASHEET_MB = 25;

function FileSlot({ component, field, canEdit }: { component: ComponentDetail; field: "image" | "datasheet"; canEdit: boolean }) {
  const qc = useQueryClient();
  const toast = useToast();
  const input = useRef<HTMLInputElement>(null);
  const url = field === "image" ? component.image_url : component.datasheet_file_url;
  const accept = field === "image" ? "image/png,image/jpeg,image/webp" : "application/pdf";
  const maxMb = field === "image" ? MAX_IMAGE_MB : MAX_DATASHEET_MB;

  const mutation = useMutation({
    mutationFn: async (file: File | null) => {
      if (file === null) return api<ComponentDetail>(`components/${component.id}/${field}`, { method: "DELETE" });
      const fd = new FormData();
      fd.append("file", file);
      return api<ComponentDetail>(`components/${component.id}/${field}`, { method: "POST", body: fd });
    },
    onSuccess: (data, file) => {
      qc.setQueryData(["component", String(component.id)], data);
      qc.invalidateQueries({ queryKey: ["components"] });
      qc.invalidateQueries({ queryKey: ["audit", "component", String(component.id)] });
      toast(file ? `${field === "image" ? "Image" : "Datasheet"} uploaded` : `${field === "image" ? "Image" : "Datasheet"} removed`);
    },
    onError: (e) => toast((e as Error).message, "error"),
  });

  const onPick = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    e.target.value = "";
    if (!file) return;
    // Client-side pre-check for UX only; the server validates type, magic bytes and size.
    if (file.size > maxMb * 1024 * 1024) { toast(`File is larger than ${maxMb} MB.`, "error"); return; }
    mutation.mutate(file);
  };

  return (
    <div className="space-y-2">
      {field === "image" ? (
        url ? (
          // eslint-disable-next-line @next/next/no-img-element -- user-uploaded media served by the backend
          <img src={url} alt={`${component.internal_part_number} image`} className="mx-auto max-h-48 rounded border border-slate-100 object-contain" />
        ) : (
          <div className="flex h-32 items-center justify-center rounded border border-dashed border-slate-200 text-slate-300"><ImageIcon className="h-8 w-8" /></div>
        )
      ) : url ? (
        <a href={url} target="_blank" rel="noopener noreferrer" className="flex items-center gap-2 text-sm text-blue-700 hover:underline">
          <FileText className="h-4 w-4" /> Open uploaded datasheet (PDF)
        </a>
      ) : (
        <p className="text-sm text-slate-500">No datasheet file uploaded.</p>
      )}
      {canEdit && (
        <div className="flex flex-wrap gap-2">
          <input ref={input} type="file" accept={accept} className="hidden" onChange={onPick} />
          <Button size="sm" variant="secondary" loading={mutation.isPending} onClick={() => input.current?.click()}>
            <Upload className="h-3.5 w-3.5" /> {url ? "Replace" : "Upload"} {field === "image" ? "image" : "PDF"}
          </Button>
          {url && (
            <Button size="sm" variant="ghost" disabled={mutation.isPending} onClick={() => { if (confirm(`Remove the ${field}?`)) mutation.mutate(null); }}>
              <Trash2 className="h-3.5 w-3.5" /> Remove
            </Button>
          )}
        </div>
      )}
      {canEdit && <p className="text-xs text-slate-400">{field === "image" ? `PNG, JPEG or WebP · max ${MAX_IMAGE_MB} MB` : `PDF · max ${MAX_DATASHEET_MB} MB`}</p>}
    </div>
  );
}

function Activity({ id }: { id: number }) {
  const { data, isLoading, error } = useQuery({
    queryKey: ["audit", "component", String(id)],
    queryFn: () => api<Paginated<AuditEntry>>("audit-logs", { query: { entity_type: "components.component", entity_id: String(id), ordering: "-timestamp", page_size: 20 } }),
  });
  if (isLoading) return <Spinner />;
  if (error) return <ErrorState message={(error as Error).message} />;
  if (!data?.results.length) return <p className="text-sm text-slate-500">No recorded activity.</p>;
  return (
    <ol className="space-y-3">
      {data.results.map((e) => {
        const changed = e.action === "UPDATE" && e.new_value ? Object.keys(e.new_value as object) : [];
        return (
          <li key={e.id} className="text-sm">
            <div className="flex flex-wrap items-center gap-x-2">
              <Badge tone={e.action === "CREATE" ? "green" : e.action === "DELETE" ? "red" : "blue"}>{e.action}</Badge>
              <span className="text-slate-700">{e.user_email || "system"}</span>
              <span className="text-xs text-slate-400" title={formatDateTime(e.timestamp)}>{formatRelative(e.timestamp)}</span>
            </div>
            {changed.length > 0 && <p className="mt-0.5 text-xs text-slate-500">Changed: {changed.join(", ")}</p>}
          </li>
        );
      })}
    </ol>
  );
}

function ComponentStock({ id }: { id: number }) {
  const { data, isLoading, error } = useQuery({
    queryKey: ["stock", "component", String(id)],
    queryFn: () =>
      api<Paginated<{
        id: number;
        warehouse_code: string;
        location_code: string | null;
        lot_batch: string;
        quantity_on_hand: string;
        quantity_reserved: string;
        quantity_available: string;
        stock_status?: string;
      }>>("inventory/stock", { query: { component: id, page_size: 50 } }),
  });
  if (isLoading) return <Spinner />;
  if (error) return <ErrorState message={(error as Error).message} />;
  if (!data?.results.length) return <p className="text-sm text-slate-500">No stock on hand across warehouses.</p>;
  return (
    <div className="overflow-x-auto">
      <table className="w-full text-sm">
        <thead className="border-b border-slate-100 text-left text-xs uppercase text-slate-500">
          <tr>
            <th className="py-1.5 pr-3">Warehouse / Bin</th>
            <th className="py-1.5 pr-3">Lot</th>
            <th className="py-1.5 pr-3">On Hand</th>
            <th className="py-1.5 pr-3">Reserved</th>
            <th className="py-1.5">Available</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-slate-100">
          {data.results.map((row) => (
            <tr key={row.id}>
              <td className="py-1.5 pr-3 font-medium">
                {row.warehouse_code}
                {row.location_code ? ` / ${row.location_code}` : ""}
              </td>
              <td className="py-1.5 pr-3 text-slate-500">{row.lot_batch || "—"}</td>
              <td className="py-1.5 pr-3">{row.quantity_on_hand}</td>
              <td className="py-1.5 pr-3">{row.quantity_reserved}</td>
              <td className="py-1.5 font-semibold text-emerald-700">{row.quantity_available}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function ComponentSuppliersAndPricing({ id }: { id: number }) {
  const [qty, setQty] = useState("10");

  const { data: cmp, isLoading } = useQuery<{
    offers: SupplierOfferComparison[];
  }>({
    queryKey: ["supplier-parts-compare", id, qty],
    queryFn: () => api("supplier-parts/compare", { query: { component: id, quantity: qty || 1 } }),
    enabled: Number(qty) > 0,
  });

  const { data: history } = useQuery<{
    purchase_orders: {
      id: number;
      purchase_order_id: number;
      po_number: string;
      po_status: string;
      supplier_name: string;
      supplier_part_number: string;
      quantity_ordered: string;
      quantity_received: string;
      unit_price: string;
      currency: string;
    }[];
  }>({
    queryKey: ["component-purchase-history", id],
    queryFn: () => api("purchasing/component-history", { query: { component: id } }),
  });

  const offers = cmp?.offers ?? [];
  const orders = history?.purchase_orders ?? [];

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <span className="text-xs font-semibold uppercase text-slate-500">Supplier Price Comparison</span>
        <div className="flex items-center gap-2 text-xs">
          <label htmlFor="cmp-qty" className="text-slate-600">Eval Qty:</label>
          <input
            id="cmp-qty"
            type="number"
            min="1"
            value={qty}
            onChange={(e) => setQty(e.target.value)}
            className="w-20 rounded border border-slate-300 px-2 py-1 font-mono text-xs"
          />
        </div>
      </div>

      {isLoading ? (
        <Spinner />
      ) : offers.length === 0 ? (
        <p className="text-sm text-slate-500">No active supplier part offerings linked to this component.</p>
      ) : (
        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs">
            <thead className="border-b border-slate-100 uppercase text-slate-500">
              <tr>
                <th className="py-1.5 pr-2">Supplier</th>
                <th className="py-1.5 pr-2">Supplier PN</th>
                <th className="py-1.5 pr-2">MOQ / Mult</th>
                <th className="py-1.5 pr-2">Order Qty</th>
                <th className="py-1.5 pr-2">Unit Price</th>
                <th className="py-1.5 text-right">Extended</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {offers.map((o) => (
                <tr key={o.supplier_part_id}>
                  <td className="py-1.5 pr-2 font-medium">
                    <Link href={`/suppliers/${o.supplier_id}`} className="text-blue-700 hover:underline">
                      {o.supplier_name}
                    </Link>
                    {o.is_preferred && <span className="ml-1.5"><Badge tone="blue">Pref</Badge></span>}
                  </td>
                  <td className="py-1.5 pr-2 font-mono">{o.supplier_part_number}</td>
                  <td className="py-1.5 pr-2 font-mono">{Number(o.moq)} / {Number(o.order_multiple)}</td>
                  <td className="py-1.5 pr-2 font-mono">{Number(o.effective_order_quantity)}</td>
                  <td className="py-1.5 pr-2 font-mono font-semibold">
                    {Number(o.effective_unit_price).toFixed(4)} {o.currency}
                  </td>
                  <td className="py-1.5 text-right font-mono font-semibold text-emerald-700">
                    {Number(o.extended_price).toFixed(2)} {o.currency}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {orders.length > 0 && (
        <div className="border-t border-slate-100 pt-3">
          <div className="mb-2 text-xs font-semibold uppercase text-slate-500">Recent Purchase Orders</div>
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs">
              <thead className="border-b border-slate-100 uppercase text-slate-500">
                <tr>
                  <th className="py-1.5 pr-2">PO #</th>
                  <th className="py-1.5 pr-2">Supplier</th>
                  <th className="py-1.5 pr-2">Received / Ordered</th>
                  <th className="py-1.5 pr-2">Unit Price</th>
                  <th className="py-1.5 text-right">Status</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {orders.slice(0, 5).map((po) => (
                  <tr key={po.id}>
                    <td className="py-1.5 pr-2 font-mono font-semibold">
                      <Link href={`/purchasing/orders/${po.purchase_order_id}`} className="text-blue-700 hover:underline">
                        {po.po_number}
                      </Link>
                    </td>
                    <td className="py-1.5 pr-2">{po.supplier_name}</td>
                    <td className="py-1.5 pr-2 font-mono">
                      {Number(po.quantity_received)} / {Number(po.quantity_ordered)}
                    </td>
                    <td className="py-1.5 pr-2 font-mono">
                      {Number(po.unit_price).toFixed(4)} {po.currency}
                    </td>
                    <td className="py-1.5 text-right">
                      <Badge tone="slate">{po.po_status}</Badge>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  );
}

export default function ComponentDetailPage() {
  const { id } = useParams<{ id: string }>();
  const router = useRouter();
  const qc = useQueryClient();
  const toast = useToast();
  const { can } = useAuth();
  const [confirmDelete, setConfirmDelete] = useState(false);

  const { data: c, isLoading, error, refetch } = useQuery({
    queryKey: ["component", id],
    queryFn: () => api<ComponentDetail>(`components/${id}`),
  });

  const del = useMutation({
    mutationFn: () => api(`components/${id}`, { method: "DELETE" }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["components"] });
      qc.invalidateQueries({ queryKey: ["dashboard"] });
      qc.removeQueries({ queryKey: ["component", id] });
      toast(`Deleted ${c?.internal_part_number}`);
      router.push("/components");
    },
    onError: (e) => { setConfirmDelete(false); toast(e instanceof ApiError ? e.message : "Delete failed.", "error"); },
  });

  if (isLoading) return <Spinner />;
  if (error || !c) {
    const notFound = error instanceof ApiError && error.status === 404;
    return <ErrorState message={notFound ? "Component not found. It may have been deleted." : (error as Error)?.message ?? "Failed to load."} onRetry={notFound ? undefined : () => refetch()} />;
  }

  const canEdit = can("component.edit");
  const aliasLabel = (t: string) => ALIAS_TYPES.find((a) => a.value === t)?.label ?? t;

  return (
    <>
      <PageHeader
        title={<span className="pn">{c.internal_part_number}</span>}
        subtitle={<><Link href="/components" className="text-blue-700 hover:underline">Components</Link> / {c.category_path}</>}
        actions={
          <>
            {canEdit && <Link href={`/components/${c.id}/edit`}><Button><Pencil className="h-4 w-4" /> Edit</Button></Link>}
            {can("component.delete") && <Button variant="secondary" onClick={() => setConfirmDelete(true)}><Trash2 className="h-4 w-4" /> Delete</Button>}
          </>
        }
      />

      <div className="grid gap-4 lg:grid-cols-3">
        <div className="space-y-4 lg:col-span-2">
          <Card title={c.name} actions={<div className="flex gap-1.5"><LifecycleBadge value={c.lifecycle_status} /><Badge tone={c.status === "ACTIVE" ? "blue" : "slate"}>{STATUS_LABELS[c.status]}</Badge></div>}>
            <DescriptionList items={[
              { label: "MPN", value: c.mpn && <span className="pn">{c.mpn}</span> },
              { label: "Manufacturer", value: c.manufacturer?.name },
              { label: "Category", value: c.category_path },
              { label: "Package", value: c.package?.name },
              { label: "RoHS", value: triState(c.is_rohs) },
              { label: "REACH", value: triState(c.is_reach) },
              { label: "Datasheet URL", value: c.datasheet_url && (
                <a href={c.datasheet_url} target="_blank" rel="noopener noreferrer" className="inline-flex items-center gap-1 text-blue-700 hover:underline">
                  Open <ExternalLink className="h-3 w-3" />
                </a>
              ) },
              { label: "Description", value: c.description },
            ]} />
            {c.notes && (
              <div className="mt-4 rounded-md bg-slate-50 p-3 text-sm whitespace-pre-wrap text-slate-700">
                <div className="mb-1 text-xs font-medium uppercase tracking-wide text-slate-500">Notes</div>
                {c.notes}
              </div>
            )}
          </Card>

          <Card title="Specifications">
            {c.specifications.length === 0 ? <p className="text-sm text-slate-500">No specification values recorded.</p> : (
              <table className="w-full text-sm">
                <tbody className="divide-y divide-slate-100">
                  {c.specifications.map((s) => (
                    <tr key={s.definition}>
                      <th scope="row" className="w-1/2 py-1.5 pr-4 text-left font-normal text-slate-500">{s.name}</th>
                      <td className="py-1.5 font-medium text-slate-900">{s.display_value}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </Card>

          <Card title="Aliases">
            {c.aliases.length === 0 ? <p className="text-sm text-slate-500">No aliases.</p> : (
              <ul className="divide-y divide-slate-100 text-sm">
                {c.aliases.map((a) => (
                  <li key={a.id ?? a.alias} className="flex items-center justify-between gap-2 py-1.5">
                    <span className="pn">{a.alias}</span>
                    <span className="text-xs text-slate-500">{aliasLabel(a.alias_type)}</span>
                  </li>
                ))}
              </ul>
            )}
          </Card>

          <Card title="Stock" actions={<Link href="/inventory/stock" className="text-xs text-blue-700 hover:underline">Manage stock</Link>}>
            <ComponentStock id={c.id} />
          </Card>
          <Card title="Suppliers & pricing" actions={<Link href="/suppliers" className="text-xs text-blue-700 hover:underline">Manage suppliers</Link>}>
            <ComponentSuppliersAndPricing id={c.id} />
          </Card>
        </div>

        <div className="space-y-4">
          <Card title="Image"><FileSlot component={c} field="image" canEdit={canEdit} /></Card>
          <Card title="Datasheet file"><FileSlot component={c} field="datasheet" canEdit={canEdit} /></Card>
          <Card title="Record">
            <DescriptionList items={[
              { label: "Created", value: `${formatDateTime(c.created_at)}${c.created_by_name ? ` · ${c.created_by_name}` : ""}` },
              { label: "Last updated", value: `${formatDateTime(c.updated_at)}${c.updated_by_name ? ` · ${c.updated_by_name}` : ""}` },
            ]} />
          </Card>
          {can("audit.view") && <Card title="Activity"><Activity id={c.id} /></Card>}
        </div>
      </div>

      <Modal
        open={confirmDelete}
        title={`Delete ${c.internal_part_number}?`}
        onClose={() => setConfirmDelete(false)}
        footer={<>
          <Button variant="secondary" onClick={() => setConfirmDelete(false)}>Cancel</Button>
          <Button variant="danger" loading={del.isPending} onClick={() => del.mutate()}>Delete component</Button>
        </>}
      >
        <p className="text-sm text-slate-600">
          The component is archived (soft-deleted): it disappears from lists and search, but its history and audit trail are kept.
          Its internal part number <span className="pn">{c.internal_part_number}</span> will never be reused.
        </p>
      </Modal>
    </>
  );
}
