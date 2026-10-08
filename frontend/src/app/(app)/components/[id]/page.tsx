"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ExternalLink, FileText, ImageIcon, Pencil, Trash2, Upload } from "lucide-react";
import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { useRef, useState } from "react";

import { Button } from "@/components/ui/button";
import { Badge, Card, DescriptionList, ErrorState, LifecycleBadge, Modal, NotImplemented, PageHeader, Spinner } from "@/components/ui/primitives";
import { useToast } from "@/components/ui/toast";
import { ApiError, api, type Paginated } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { ALIAS_TYPES, STATUS_LABELS, type AuditEntry, type ComponentDetail } from "@/lib/types";
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
  const { data, isLoading, error } = useQuery<any>({
    queryKey: ["audit", "component", String(id)],
    queryFn: () => api<Paginated<AuditEntry>>("audit-logs", { query: { entity_type: "components.component", entity_id: String(id), ordering: "-timestamp", page_size: 20 } }),
  });
  if (isLoading) return <Spinner />;
  if (error) return <ErrorState message={(error as Error).message} />;
  if (!data?.results.length) return <p className="text-sm text-slate-500">No recorded activity.</p>;
  return (
    <ol className="space-y-3">
      {data.results.map((e: any) => {
        const changed = e.action === "UPDATE" && e.new_value ? Object.keys(e.new_value) : [];
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

export default function ComponentDetailPage() {
  const { id } = useParams<{ id: string }>();
  const router = useRouter();
  const qc = useQueryClient();
  const toast = useToast();
  const { can } = useAuth();
  const [confirmDelete, setConfirmDelete] = useState(false);

  const { data: c, isLoading, error, refetch } = useQuery<any>({
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
          <Card title={c.name} actions={<div className="flex gap-1.5"><LifecycleBadge value={c.lifecycle_status} /><Badge tone={c.status === "ACTIVE" ? "blue" : "slate"}>{STATUS_LABELS[c.status as keyof typeof STATUS_LABELS]}</Badge></div>}>
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
                  {c.specifications.map((s: any) => (
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
                {c.aliases.map((a: any) => (
                  <li key={a.id ?? a.alias} className="flex items-center justify-between gap-2 py-1.5">
                    <span className="pn">{a.alias}</span>
                    <span className="text-xs text-slate-500">{aliasLabel(a.alias_type)}</span>
                  </li>
                ))}
              </ul>
            )}
          </Card>

          <Card title="Where used"><NotImplemented feature="BOM where-used" phase={2} /></Card>
          <Card title="Stock"><NotImplemented feature="Inventory / stock levels" phase={3} /></Card>
          <Card title="Suppliers & pricing"><NotImplemented feature="Supplier parts and pricing" phase={4} /></Card>
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
