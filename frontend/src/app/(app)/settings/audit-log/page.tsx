"use client";

import { keepPreviousData, useQuery } from "@tanstack/react-query";
import Link from "next/link";
import { useState } from "react";

import { DataTable, type Column } from "@/components/data-table/data-table";
import { Select } from "@/components/ui/form";
import { Badge, EmptyState, Forbidden, Modal, PageHeader } from "@/components/ui/primitives";
import { api, fetchAllPages, type Paginated } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import type { AuditEntry } from "@/lib/types";
import { formatDateTime } from "@/lib/utils";
import { useListState } from "@/lib/use-list-state";

const ACTIONS = ["CREATE", "UPDATE", "DELETE", "RESTORE", "LOGIN", "LOGOUT", "LOGIN_FAILED", "PERMISSION_CHANGE", "PASSWORD_CHANGE", "FILE_UPLOAD", "FILE_DELETE"];
const tone = (a: string) => (a === "CREATE" ? "green" : a === "DELETE" || a === "LOGIN_FAILED" ? "red" : a.startsWith("PERMISSION") ? "amber" : "blue");

function entityLink(e: AuditEntry): string | null {
  if (e.entity_type === "components.component" && e.action !== "DELETE") return `/components/${e.entity_id}`;
  return null;
}

export default function AuditLogPage() {
  const { can } = useAuth();
  const allowed = can("audit.view");
  const list = useListState({ ordering: "-timestamp" });
  const [open, setOpen] = useState<AuditEntry | null>(null);
  const { data, isFetching, error, refetch } = useQuery({
    queryKey: ["audit-logs", list.query],
    queryFn: () => api<Paginated<AuditEntry>>("audit-logs", { query: list.query }),
    placeholderData: keepPreviousData,
    enabled: allowed,
  });
  if (!allowed) return <Forbidden permission="audit.view" />;

  const columns: Column<AuditEntry>[] = [
    { key: "ts", header: "Time", sortKey: "timestamp", render: (e) => <span className="whitespace-nowrap text-slate-600">{formatDateTime(e.timestamp)}</span>, csv: (e) => e.timestamp },
    { key: "user", header: "User", render: (e) => e.user_email || "system", csv: (e) => e.user_email },
    { key: "action", header: "Action", sortKey: "action", render: (e) => <Badge tone={tone(e.action)}>{e.action}</Badge>, csv: (e) => e.action },
    { key: "type", header: "Entity type", sortKey: "entity_type", render: (e) => <span className="pn text-xs">{e.entity_type}</span>, csv: (e) => e.entity_type },
    { key: "entity", header: "Entity", render: (e) => { const href = entityLink(e); return href ? <Link href={href} onClick={(ev) => ev.stopPropagation()} className="text-blue-700 hover:underline">{e.entity_repr || e.entity_id}</Link> : (e.entity_repr || e.entity_id || "—"); }, csv: (e) => e.entity_repr },
    { key: "ip", header: "IP", render: (e) => <span className="text-slate-500">{e.ip_address ?? "—"}</span>, csv: (e) => e.ip_address, hiddenByDefault: true },
    { key: "detail", header: "", render: (e) => <button className="text-xs text-blue-700 hover:underline" onClick={() => setOpen(e)}>Details</button> },
  ];

  return (
    <>
      <PageHeader title="Audit log" subtitle={<><Link href="/settings" className="text-blue-700 hover:underline">Settings</Link> / Audit log — append-only record of changes and security events</>} />
      <DataTable
        id="audit" exportName="audit-log" columns={columns} rows={data?.results} count={data?.count ?? 0}
        page={list.page} pageSize={list.pageSize} ordering={list.ordering} loading={isFetching}
        error={error ? (error as Error).message : null} onRetry={() => refetch()}
        search={list.search} onSearch={(s) => list.update({ search: s })} searchPlaceholder="Search entity, user email, id…"
        onOrdering={(o) => list.update({ ordering: o })} onPage={(p) => list.update({ page: p }, false)} onPageSize={(s) => list.update({ page_size: s })}
        rowKey={(e) => e.id}
        toolbar={<Select aria-label="Action" className="h-8 w-auto text-xs" value={list.filters.action ?? ""} onChange={(e) => list.update({ action: e.target.value })}>
          <option value="">Action: all</option>{ACTIONS.map((a) => <option key={a} value={a}>{a}</option>)}
        </Select>}
        mobileCard={(e) => (
          <button className="w-full text-left" onClick={() => setOpen(e)}>
            <div className="flex items-center justify-between"><Badge tone={tone(e.action)}>{e.action}</Badge><span className="text-xs text-slate-500">{formatDateTime(e.timestamp)}</span></div>
            <div className="mt-1 text-sm">{e.entity_repr || e.entity_type}</div>
            <div className="text-xs text-slate-500">{e.user_email || "system"}</div>
          </button>
        )}
        onExport={() => fetchAllPages<AuditEntry>("audit-logs", { ...list.query, page: undefined, page_size: undefined })}
        empty={<EmptyState title="No audit entries" />}
      />
      <Modal open={!!open} onClose={() => setOpen(null)} title={open ? `${open.action} · ${open.entity_repr || open.entity_type}` : ""} wide>
        {open && (
          <div className="space-y-3 text-sm">
            <p className="text-slate-600">{formatDateTime(open.timestamp)} · {open.user_email || "system"} · {open.ip_address ?? "no IP"}</p>
            {(["old_value", "new_value", "metadata"] as const).map((k) => open[k] && Object.keys(open[k]!).length > 0 && (
              <div key={k}>
                <div className="mb-1 text-xs font-medium uppercase text-slate-500">{k.replace("_", " ")}</div>
                <pre className="max-h-64 overflow-auto rounded bg-slate-50 p-2 text-xs">{JSON.stringify(open[k], null, 2)}</pre>
              </div>
            ))}
          </div>
        )}
      </Modal>
    </>
  );
}
