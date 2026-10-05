"use client";

import { ScrollText } from "lucide-react";
import Link from "next/link";
import { useState } from "react";

import { Button } from "@/components/ui/button";
import { Field, Input } from "@/components/ui/form";
import { Badge, Card, DescriptionList, ErrorState, NotImplemented, PageHeader } from "@/components/ui/primitives";
import { useToast } from "@/components/ui/toast";
import { ApiError, api, type FieldErrors } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { formatDateTime } from "@/lib/utils";

function ChangePassword() {
  const toast = useToast();
  const [current, setCurrent] = useState("");
  const [next, setNext] = useState("");
  const [confirm, setConfirm] = useState("");
  const [errors, setErrors] = useState<FieldErrors>({});
  const [formError, setFormError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    setErrors({}); setFormError(null);
    if (next !== confirm) { setErrors({ confirm: ["Passwords do not match."] }); return; }
    setSaving(true);
    try {
      await api("auth/change-password", { method: "POST", body: { current_password: current, new_password: next } });
      setCurrent(""); setNext(""); setConfirm("");
      toast("Password changed");
    } catch (err) {
      if (err instanceof ApiError) {
        setErrors(err.fieldErrors);
        // Django password validators return a list under non_field_errors / new_password
        if (!err.fieldErrors.current_password && !err.fieldErrors.new_password) setFormError(err.message);
      } else setFormError("Unexpected error.");
    } finally { setSaving(false); }
  };

  return (
    <form onSubmit={submit} className="max-w-md space-y-3" noValidate>
      {formError && <ErrorState message={formError} />}
      <Field label="Current password" htmlFor="cp-current" error={errors.current_password}>
        <Input id="cp-current" type="password" autoComplete="current-password" value={current} onChange={(e) => setCurrent(e.target.value)} invalid={!!errors.current_password} />
      </Field>
      <Field label="New password" htmlFor="cp-new" error={errors.new_password} hint="Min. 10 characters; not a common or all-numeric password.">
        <Input id="cp-new" type="password" autoComplete="new-password" value={next} onChange={(e) => setNext(e.target.value)} invalid={!!errors.new_password} />
      </Field>
      <Field label="Confirm new password" htmlFor="cp-confirm" error={errors.confirm}>
        <Input id="cp-confirm" type="password" autoComplete="new-password" value={confirm} onChange={(e) => setConfirm(e.target.value)} invalid={!!errors.confirm} />
      </Field>
      <Button type="submit" loading={saving} disabled={!current || !next}>Change password</Button>
    </form>
  );
}

export default function SettingsPage() {
  const { user, can } = useAuth();
  if (!user) return null;
  return (
    <>
      <PageHeader title="Settings" />
      <div className="grid gap-4 lg:grid-cols-2">
        <Card title="My profile">
          <DescriptionList items={[
            { label: "Name", value: user.full_name },
            { label: "Email", value: user.email },
            { label: "Job title", value: user.job_title },
            { label: "Department", value: user.department },
            { label: "Roles", value: <div className="flex flex-wrap gap-1">{user.roles.map((r) => <Badge key={r.code} tone="violet">{r.name}</Badge>)}</div> },
            { label: "Last login", value: formatDateTime(user.last_login) },
          ]} />
          <p className="mt-3 text-xs text-slate-500">Profile details are managed by an administrator under Users.</p>
        </Card>
        <Card title="Change password"><ChangePassword /></Card>
        {can("audit.view") && (
          <Card title="Administration">
            <Link href="/settings/audit-log" className="flex items-center gap-2 text-sm text-blue-700 hover:underline"><ScrollText className="h-4 w-4" /> Audit log</Link>
          </Card>
        )}
        <Card title="Notifications"><NotImplemented feature="Notification preferences" phase={5} /></Card>
      </div>
    </>
  );
}
