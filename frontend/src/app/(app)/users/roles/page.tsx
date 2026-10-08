"use client";

import { useQuery, useQueryClient } from "@tanstack/react-query";
import { Lock } from "lucide-react";
import Link from "next/link";
import { useEffect, useMemo, useState } from "react";

import { Button } from "@/components/ui/button";
import { Badge, Card, ErrorState, Forbidden, PageHeader, Spinner } from "@/components/ui/primitives";
import { useToast } from "@/components/ui/toast";
import { api, type Paginated } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import type { Permission, Role } from "@/lib/types";
import { cn } from "@/lib/utils";

export default function RolesPage() {
  const { can } = useAuth();
  const qc = useQueryClient();
  const toast = useToast();
  const allowed = can("user.manage") || can("role.manage");
  const canEdit = can("role.manage");
  const [selected, setSelected] = useState<number | null>(null);
  const [draft, setDraft] = useState<Set<string>>(new Set());
  const [saving, setSaving] = useState(false);

  const roles = useQuery<any>({ queryKey: ["roles"], queryFn: async () => (await api<Paginated<Role>>("roles", { query: { page_size: 200, ordering: "name" } })).results, enabled: allowed });
  const perms = useQuery<any>({ queryKey: ["permissions"], queryFn: () => api<Permission[]>("permissions"), enabled: allowed });

  const role = roles.data?.find((r: any) => r.id === selected) ?? roles.data?.[0];
  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect -- load the selected role's permissions into the editable draft
    if (role) setDraft(new Set(role.permission_codes));
  }, [role]);

  const byModule = useMemo(() => {
    const m = new Map<string, Permission[]>();
    perms.data?.forEach((p: any) => m.set(p.module, [...(m.get(p.module) ?? []), p]));
    return [...m.entries()];
  }, [perms.data]);

  if (!allowed) return <Forbidden permission="user.manage" />;
  if (roles.isLoading || perms.isLoading) return <Spinner />;
  if (roles.error || perms.error) return <ErrorState message={((roles.error ?? perms.error) as Error).message} />;

  const isSuper = role?.code === "SUPER_ADMIN";
  const dirty = role && (draft.size !== role.permission_codes.length || role.permission_codes.some((c: any) => !draft.has(c)));

  const save = async () => {
    if (!role) return;
    setSaving(true);
    try {
      await api(`roles/${role.id}/permissions`, { method: "PUT", body: { permission_codes: [...draft].sort() } });
      await qc.invalidateQueries({ queryKey: ["roles"] });
      qc.invalidateQueries({ queryKey: ["me"] });
      toast(`Permissions updated for ${role.name}`);
    } catch (e) {
      toast((e as Error).message, "error");
    } finally { setSaving(false); }
  };

  return (
    <>
      <PageHeader title="Roles & permissions" subtitle={<><Link href="/users" className="text-blue-700 hover:underline">Users</Link> / Roles. Permissions are enforced by the API on every request.</>} />
      <div className="grid gap-4 lg:grid-cols-4">
        <Card title="Roles" className="lg:col-span-1">
          <ul className="-mx-2 space-y-0.5">
            {roles.data?.map((r: any) => (
              <li key={r.id}>
                <button onClick={() => setSelected(r.id)} className={cn("flex w-full items-center justify-between rounded px-2 py-1.5 text-left text-sm", role?.id === r.id ? "bg-blue-50 text-blue-800" : "hover:bg-slate-50")}>
                  <span>{r.name}</span><span className="text-xs text-slate-400">{r.user_count}</span>
                </button>
              </li>
            ))}
          </ul>
        </Card>
        {role && (
          <Card className="lg:col-span-3" title={<span className="flex items-center gap-2">{role.name} <span className="pn text-xs font-normal text-slate-400">{role.code}</span>{role.is_system && <Badge>System</Badge>}</span>}
            actions={canEdit && !isSuper && <Button size="sm" disabled={!dirty} loading={saving} onClick={save}>Save permissions</Button>}>
            <p className="mb-3 text-sm text-slate-500">{role.description}</p>
            {isSuper && <p className="mb-3 flex items-center gap-1.5 text-sm text-amber-800"><Lock className="h-3.5 w-3.5" /> Super Admin implicitly has every permission and cannot be restricted.</p>}
            <div className="grid gap-4 sm:grid-cols-2">
              {byModule.map(([module, list]) => (
                <fieldset key={module} className="rounded border border-slate-200 p-3">
                  <legend className="px-1 text-xs font-semibold uppercase tracking-wide text-slate-500">{module}</legend>
                  <div className="space-y-1.5">
                    {list.map((p) => (
                      <label key={p.code} className="flex items-start gap-2 text-sm">
                        <input type="checkbox" className="mt-0.5 h-4 w-4" disabled={!canEdit || isSuper}
                          checked={isSuper || draft.has(p.code)}
                          onChange={(e) => setDraft((s) => { const n = new Set(s); if (e.target.checked) n.add(p.code); else n.delete(p.code); return n; })} />
                        <span><span className="pn text-xs text-slate-800">{p.code}</span><span className="block text-xs text-slate-500">{p.name}</span></span>
                      </label>
                    ))}
                  </div>
                </fieldset>
              ))}
            </div>
          </Card>
        )}
      </div>
    </>
  );
}
