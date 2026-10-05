"use client";

import { keepPreviousData, useQuery, useQueryClient } from "@tanstack/react-query";
import { KeyRound, Pencil, Plus } from "lucide-react";
import Link from "next/link";
import { useEffect, useState } from "react";

import { DataTable, type Column } from "@/components/data-table/data-table";
import { Button } from "@/components/ui/button";
import { Field, Input, Select } from "@/components/ui/form";
import { Badge, EmptyState, ErrorState, Forbidden, Modal, PageHeader } from "@/components/ui/primitives";
import { useToast } from "@/components/ui/toast";
import { ApiError, api, type FieldErrors, type Paginated } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import type { Role, User } from "@/lib/types";
import { formatDateTime } from "@/lib/utils";
import { useListState } from "@/lib/use-list-state";

const PROFILE_FIELDS = [
  ["email", "Email", "email"], ["first_name", "First name", "text"], ["last_name", "Last name", "text"],
  ["job_title", "Job title", "text"], ["department", "Department", "text"], ["phone", "Phone", "tel"],
] as const;

function useRoles() {
  return useQuery({ queryKey: ["roles"], queryFn: async () => (await api<Paginated<Role>>("roles", { query: { page_size: 200, ordering: "name" } })).results });
}

function UserModal({ user, open, onClose }: { user: User | null; open: boolean; onClose: () => void }) {
  const qc = useQueryClient();
  const toast = useToast();
  const { data: roles } = useRoles();
  const [v, setV] = useState<Record<string, string>>({});
  const [roleCodes, setRoleCodes] = useState<string[]>([]);
  const [active, setActive] = useState(true);
  const [errors, setErrors] = useState<FieldErrors>({});
  const [formError, setFormError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    if (!open) return;
    // eslint-disable-next-line react-hooks/set-state-in-effect -- reset form when opened
    setV(Object.fromEntries(PROFILE_FIELDS.map(([k]) => [k, user?.[k] ?? ""])));
    setRoleCodes(user?.roles.map((r) => r.code) ?? []);
    setActive(user?.is_active ?? true);
    setErrors({});
    setFormError(null);
  }, [open, user]);

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    setSaving(true);
    setErrors({});
    setFormError(null);
    const body: Record<string, unknown> = { ...v, role_codes: roleCodes, is_active: active };
    if (!user) body.password = v.password ?? "";
    try {
      await api(user ? `users/${user.id}` : "users", { method: user ? "PATCH" : "POST", body });
      qc.invalidateQueries({ queryKey: ["users"] });
      qc.invalidateQueries({ queryKey: ["roles"] });
      qc.invalidateQueries({ queryKey: ["me"] });
      toast(user ? "User saved" : "User created");
      onClose();
    } catch (err) {
      if (err instanceof ApiError) { setErrors(err.fieldErrors); setFormError(err.message); } else setFormError("Unexpected error.");
    } finally { setSaving(false); }
  };

  return (
    <Modal open={open} onClose={onClose} title={user ? `Edit ${user.email}` : "Add user"} wide
      footer={<><Button variant="secondary" onClick={onClose}>Cancel</Button><Button type="submit" form="user-form" loading={saving}>{user ? "Save" : "Create user"}</Button></>}>
      <form id="user-form" onSubmit={submit} noValidate className="grid gap-4 sm:grid-cols-2">
        {formError && <div className="sm:col-span-2"><ErrorState message={formError} /></div>}
        {PROFILE_FIELDS.map(([k, label, type]) => (
          <Field key={k} label={label} htmlFor={`u-${k}`} required={k === "email"} error={errors[k]}>
            <Input id={`u-${k}`} type={type} invalid={!!errors[k]} value={v[k] ?? ""} onChange={(e) => setV((s) => ({ ...s, [k]: e.target.value }))} />
          </Field>
        ))}
        {!user && (
          <Field label="Initial password" htmlFor="u-password" required error={errors.password} hint="Min. 10 characters; checked against common-password lists.">
            <Input id="u-password" type="password" autoComplete="new-password" invalid={!!errors.password} value={v.password ?? ""} onChange={(e) => setV((s) => ({ ...s, password: e.target.value }))} />
          </Field>
        )}
        <label className="flex items-center gap-2 self-end text-sm text-slate-700">
          <input type="checkbox" className="h-4 w-4" checked={active} onChange={(e) => setActive(e.target.checked)} /> Active (can sign in)
        </label>
        <fieldset className="sm:col-span-2">
          <legend className="mb-1 text-sm font-medium text-slate-700">Roles</legend>
          {errors.role_codes && <p className="text-xs text-red-600">{errors.role_codes.join(" ")}</p>}
          {errors.roles && <p className="text-xs text-red-600">{errors.roles.join(" ")}</p>}
          <div className="grid gap-2 sm:grid-cols-2">
            {roles?.map((r) => (
              <label key={r.code} className="flex items-start gap-2 rounded border border-slate-200 p-2 text-sm">
                <input type="checkbox" className="mt-0.5 h-4 w-4" checked={roleCodes.includes(r.code)}
                  onChange={(e) => setRoleCodes((s) => e.target.checked ? [...s, r.code] : s.filter((c) => c !== r.code))} />
                <span><span className="font-medium">{r.name}</span><span className="block text-xs text-slate-500">{r.description}</span></span>
              </label>
            ))}
          </div>
        </fieldset>
      </form>
    </Modal>
  );
}

function PasswordModal({ user, onClose }: { user: User | null; onClose: () => void }) {
  const toast = useToast();
  const [pw, setPw] = useState("");
  const [err, setErr] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  // State resets because the parent remounts this modal with key={user.id}.
  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!user) return;
    setSaving(true); setErr(null);
    try {
      await api(`users/${user.id}/set-password`, { method: "POST", body: { password: pw } });
      toast(`Password updated for ${user.email}`);
      onClose();
    } catch (e2) { setErr((e2 as Error).message); } finally { setSaving(false); }
  };
  return (
    <Modal open={!!user} onClose={onClose} title={`Set password — ${user?.email ?? ""}`}
      footer={<><Button variant="secondary" onClick={onClose}>Cancel</Button><Button type="submit" form="pw-form" loading={saving}>Set password</Button></>}>
      <form id="pw-form" onSubmit={submit} className="space-y-3">
        {err && <ErrorState message={err} />}
        <Field label="New password" htmlFor="pw-new" hint="The user's other sessions are not signed out automatically.">
          <Input id="pw-new" type="password" autoComplete="new-password" value={pw} onChange={(e) => setPw(e.target.value)} />
        </Field>
      </form>
    </Modal>
  );
}

export default function UsersPage() {
  const { can } = useAuth();
  const list = useListState({ ordering: "email" });
  const [editing, setEditing] = useState<User | null | undefined>(undefined);
  const [pwUser, setPwUser] = useState<User | null>(null);
  const { data: roles } = useRoles();

  const allowed = can("user.manage");
  const { data, isFetching, error, refetch } = useQuery({
    queryKey: ["users", list.query],
    queryFn: () => api<Paginated<User>>("users", { query: list.query }),
    placeholderData: keepPreviousData,
    enabled: allowed,
  });
  if (!allowed) return <Forbidden permission="user.manage" />;

  const columns: Column<User>[] = [
    { key: "email", header: "Email", sortKey: "email", render: (u) => <span className="font-medium text-slate-900">{u.email}</span>, csv: (u) => u.email },
    { key: "name", header: "Name", sortKey: "first_name", render: (u) => u.full_name || "—", csv: (u) => u.full_name },
    { key: "dept", header: "Department", render: (u) => u.department || "—", csv: (u) => u.department },
    { key: "roles", header: "Roles", render: (u) => <div className="flex flex-wrap gap-1">{u.roles.map((r) => <Badge key={r.code} tone="violet">{r.name}</Badge>)}</div>, csv: (u) => u.roles.map((r) => r.code).join(" ") },
    { key: "active", header: "Status", render: (u) => u.is_active ? <Badge tone="green">Active</Badge> : <Badge tone="red">Inactive</Badge>, csv: (u) => (u.is_active ? "active" : "inactive") },
    { key: "login", header: "Last login", sortKey: "last_login", render: (u) => <span className="whitespace-nowrap text-slate-500">{formatDateTime(u.last_login)}</span>, csv: (u) => u.last_login },
    { key: "actions", header: "", render: (u) => (
      <div className="flex justify-end gap-1">
        <Button size="sm" variant="ghost" aria-label={`Edit ${u.email}`} onClick={() => setEditing(u)}><Pencil className="h-3.5 w-3.5" /></Button>
        <Button size="sm" variant="ghost" aria-label={`Set password for ${u.email}`} onClick={() => setPwUser(u)}><KeyRound className="h-3.5 w-3.5" /></Button>
      </div>
    ) },
  ];

  return (
    <>
      <PageHeader title="Users" subtitle="Accounts and role assignments. Users are deactivated, never deleted."
        actions={<>
          <Link href="/users/roles"><Button variant="secondary">Roles & permissions</Button></Link>
          <Button onClick={() => setEditing(null)}><Plus className="h-4 w-4" /> Add user</Button>
        </>} />
      <DataTable
        id="users" exportName="users" columns={columns} rows={data?.results} count={data?.count ?? 0}
        page={list.page} pageSize={list.pageSize} ordering={list.ordering} loading={isFetching}
        error={error ? (error as Error).message : null} onRetry={() => refetch()}
        search={list.search} onSearch={(s) => list.update({ search: s })} searchPlaceholder="Search email, name, department…"
        onOrdering={(o) => list.update({ ordering: o })} onPage={(p) => list.update({ page: p }, false)} onPageSize={(s) => list.update({ page_size: s })}
        rowKey={(u) => u.id}
        toolbar={<>
          <Select aria-label="Role" className="h-8 w-auto text-xs" value={list.filters.roles__code ?? ""} onChange={(e) => list.update({ roles__code: e.target.value })}>
            <option value="">Role: all</option>
            {roles?.map((r) => <option key={r.code} value={r.code}>{r.name}</option>)}
          </Select>
          <Select aria-label="Status" className="h-8 w-auto text-xs" value={list.filters.is_active ?? ""} onChange={(e) => list.update({ is_active: e.target.value })}>
            <option value="">Status: all</option><option value="true">Active</option><option value="false">Inactive</option>
          </Select>
        </>}
        mobileCard={(u) => (
          <div className="flex items-center justify-between gap-2">
            <div className="min-w-0"><div className="truncate font-medium">{u.email}</div><div className="text-xs text-slate-500">{u.roles.map((r) => r.name).join(", ") || "No roles"}{!u.is_active && " · inactive"}</div></div>
            <Button size="sm" variant="ghost" aria-label="Edit" onClick={() => setEditing(u)}><Pencil className="h-3.5 w-3.5" /></Button>
          </div>
        )}
        empty={<EmptyState title="No users found" />}
      />
      <UserModal open={editing !== undefined} user={editing ?? null} onClose={() => setEditing(undefined)} />
      <PasswordModal key={pwUser?.id ?? "none"} user={pwUser} onClose={() => setPwUser(null)} />
    </>
  );
}
