"use client";

import { useQuery } from "@tanstack/react-query";
import { Plus } from "lucide-react";
import Link from "next/link";

import { Button } from "@/components/ui/button";
import { Card, EmptyState, ErrorState, LifecycleBadge, PageHeader, Spinner } from "@/components/ui/primitives";
import { api } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import type { DashboardData, Metric } from "@/lib/types";
import { formatRelative } from "@/lib/utils";

const METRICS: { key: string; label: string; href?: string }[] = [
  { key: "total_components", label: "Total components", href: "/components" },
  { key: "active_components", label: "Active components", href: "/components?status=ACTIVE" },
  { key: "obsolete_components", label: "Obsolete", href: "/components?lifecycle_status=OBSOLETE" },
  { key: "nrnd_components", label: "NRND / Last-time-buy" },
  { key: "projects", label: "Projects" },
  { key: "active_boms", label: "Active BOMs" },
  { key: "low_stock", label: "Low stock" },
  { key: "out_of_stock", label: "Out of stock" },
  { key: "pending_purchase_requests", label: "Pending PRs" },
  { key: "pending_purchase_orders", label: "Pending POs" },
  { key: "inventory_value", label: "Inventory value" },
];

function MetricCard({ label, metric, href }: { label: string; metric?: Metric; href?: string }) {
  const body = (
    <div className="h-full rounded-lg border border-slate-200 bg-white p-3">
      <div className="text-xs font-medium text-slate-500">{label}</div>
      {metric?.available ? (
        <div className="mt-1 text-2xl font-semibold tabular-nums text-slate-900">{metric.value?.toLocaleString()}</div>
      ) : (
        <div className="mt-1.5 text-xs text-slate-400">Not available — Phase {metric?.phase ?? "?"}</div>
      )}
    </div>
  );
  return href && metric?.available ? <Link href={href} className="block hover:opacity-80">{body}</Link> : body;
}

const ACTION_VERB: Record<string, string> = { CREATE: "created", UPDATE: "updated", DELETE: "deleted", FILE_UPLOAD: "uploaded a file to",
  FILE_DELETE: "removed a file from", LOGIN: "signed in", LOGOUT: "signed out", LOGIN_FAILED: "failed sign-in", PERMISSION_CHANGE: "changed roles of",
  PASSWORD_CHANGE: "changed password of" };

export default function DashboardPage() {
  const { user, can } = useAuth();
  const { data, isLoading, error, refetch } = useQuery<any>({ queryKey: ["dashboard"], queryFn: () => api<DashboardData>("dashboard") });

  return (
    <>
      <PageHeader
        title={`Welcome, ${user?.first_name || user?.full_name}`}
        subtitle="Engineering overview"
        actions={can("component.create") && (
          <Link href="/components/new"><Button><Plus className="h-4 w-4" /> Add component</Button></Link>
        )}
      />
      {error ? <ErrorState message={(error as Error).message} onRetry={() => refetch()} /> : isLoading || !data ? <Spinner /> : (
        <div className="space-y-4">
          <div className="grid grid-cols-2 gap-2 sm:grid-cols-3 lg:grid-cols-4 xl:grid-cols-6">
            {METRICS.map((m) => <MetricCard key={m.key} label={m.label} metric={data.metrics[m.key]} href={m.href} />)}
          </div>
          <div className="grid gap-4 lg:grid-cols-2">
            <Card title="Recently updated components" actions={<Link href="/components?ordering=-updated_at" className="text-xs text-blue-700 hover:underline">View all</Link>}>
              {data.recent_components.length === 0 ? <EmptyState title="No components yet" /> : (
                <ul className="-my-2 divide-y divide-slate-100">
                  {data.recent_components.map((c) => (
                    <li key={c.id}>
                      <Link href={`/components/${c.id}`} className="flex items-center gap-3 py-2 hover:bg-slate-50">
                        <div className="min-w-0 flex-1">
                          <div className="flex items-center gap-2"><span className="pn text-blue-700">{c.internal_part_number}</span>
                            <span className="truncate text-sm text-slate-800">{c.mpn || c.name}</span></div>
                          <div className="truncate text-xs text-slate-500">{[c.manufacturer, c.category].filter(Boolean).join(" · ")}</div>
                        </div>
                        <LifecycleBadge value={c.lifecycle_status} />
                        <span className="hidden w-20 text-right text-xs text-slate-400 sm:block">{formatRelative(c.updated_at)}</span>
                      </Link>
                    </li>
                  ))}
                </ul>
              )}
            </Card>
            <Card title="Recent activity" actions={can("audit.view") && <Link href="/settings/audit-log" className="text-xs text-blue-700 hover:underline">Audit log</Link>}>
              {data.recent_activity.length === 0 ? <EmptyState title="No activity yet" /> : (
                <ul className="-my-2 divide-y divide-slate-100">
                  {data.recent_activity.map((a) => (
                    <li key={a.id} className="py-2 text-sm">
                      <span className="font-medium text-slate-800">{a.user_email || "system"}</span>{" "}
                      <span className="text-slate-600">{ACTION_VERB[a.action] ?? a.action.toLowerCase()}</span>{" "}
                      <span className="text-slate-800">{a.entity_repr || `${a.entity_type} #${a.entity_id}`}</span>
                      <div className="text-xs text-slate-400">{a.entity_type.split(".")[1]} · {formatRelative(a.timestamp)}</div>
                    </li>
                  ))}
                </ul>
              )}
            </Card>
          </div>
          <div className="grid gap-4 lg:grid-cols-2">
            <Card title="Low stock"><p className="text-sm text-slate-500">Inventory is not implemented yet (Phase 3).</p></Card>
            <Card title="Recent purchases"><p className="text-sm text-slate-500">Purchasing is not implemented yet (Phase 4).</p></Card>
          </div>
        </div>
      )}
    </>
  );
}
