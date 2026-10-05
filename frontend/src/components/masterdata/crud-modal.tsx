"use client";

import { useQueryClient } from "@tanstack/react-query";
import { useEffect, useState } from "react";

import { Button } from "@/components/ui/button";
import { Field, Input, Select, Textarea } from "@/components/ui/form";
import { ErrorState, Modal } from "@/components/ui/primitives";
import { useToast } from "@/components/ui/toast";
import { ApiError, api, type FieldErrors } from "@/lib/api";

export type FieldSpec =
  | { name: string; label: string; type: "text" | "url" | "number" | "textarea"; required?: boolean; hint?: string; placeholder?: string; className?: string; uppercase?: boolean }
  | { name: string; label: string; type: "select"; options: { value: string; label: string }[]; required?: boolean; hint?: string; className?: string }
  | { name: string; label: string; type: "checkbox"; hint?: string; className?: string }
  | { name: string; label: string; type: "list"; hint?: string; placeholder?: string; className?: string };

type Values = Record<string, string | boolean>;

function toForm(fields: FieldSpec[], initialObj?: object): Values {
  const initial = initialObj as Record<string, unknown> | undefined;
  const v: Values = {};
  for (const f of fields) {
    const raw = initial?.[f.name];
    if (f.type === "checkbox") v[f.name] = Boolean(raw);
    else if (f.type === "list") v[f.name] = Array.isArray(raw) ? raw.join("\n") : "";
    else v[f.name] = raw === null || raw === undefined ? "" : String(raw);
  }
  return v;
}

function toPayload(fields: FieldSpec[], v: Values): Record<string, unknown> {
  const out: Record<string, unknown> = {};
  for (const f of fields) {
    const raw = v[f.name];
    if (f.type === "checkbox") out[f.name] = Boolean(raw);
    else if (f.type === "list") out[f.name] = String(raw).split(/\r?\n/).map((s) => s.trim()).filter(Boolean);
    else if (f.type === "number") out[f.name] = raw === "" ? null : Number(raw);
    else if (f.type === "select" && f.name === "parent") out[f.name] = raw === "" ? null : Number(raw);
    else out[f.name] = typeof raw === "string" ? raw.trim() : raw;
  }
  return out;
}

/**
 * Generic create/edit modal for simple master-data records.
 * Validation is enforced by the API; server field errors are shown inline.
 */
export function CrudModal({ open, onClose, title, endpoint, id, fields, initial, invalidate, extraPayload }: {
  open: boolean;
  onClose: () => void;
  title: string;
  endpoint: string;
  id?: number | null;
  fields: FieldSpec[];
  initial?: object;
  invalidate: string[][];
  extraPayload?: Record<string, unknown>;
}) {
  const qc = useQueryClient();
  const toast = useToast();
  const [values, setValues] = useState<Values>(() => toForm(fields, initial));
  const [errors, setErrors] = useState<FieldErrors>({});
  const [formError, setFormError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    if (!open) return;
    setValues(toForm(fields, initial));
    setErrors({});
    setFormError(null);
    // eslint-disable-next-line react-hooks/exhaustive-deps -- only reset on open / record change
  }, [open, id]);

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    setSaving(true);
    setErrors({});
    setFormError(null);
    try {
      await api(id ? `${endpoint}/${id}` : endpoint, { method: id ? "PATCH" : "POST", body: { ...toPayload(fields, values), ...extraPayload } });
      invalidate.forEach((k) => qc.invalidateQueries({ queryKey: k }));
      toast(id ? "Saved" : "Created");
      onClose();
    } catch (err) {
      if (err instanceof ApiError) {
        setErrors(err.fieldErrors);
        const known = fields.some((f) => err.fieldErrors[f.name]);
        setFormError(known ? "Please fix the highlighted fields." : err.message);
      } else setFormError("Unexpected error.");
    } finally {
      setSaving(false);
    }
  };

  const set = (name: string, v: string | boolean) => setValues((s) => ({ ...s, [name]: v }));

  return (
    <Modal open={open} onClose={onClose} title={title} wide={fields.length > 5}
      footer={<>
        <Button variant="secondary" onClick={onClose}>Cancel</Button>
        <Button type="submit" form="crud-form" loading={saving}>{id ? "Save" : "Create"}</Button>
      </>}>
      <form id="crud-form" onSubmit={submit} noValidate className="grid gap-4 sm:grid-cols-2">
        {formError && <div className="sm:col-span-2"><ErrorState message={formError} /></div>}
        {fields.map((f) => {
          const fid = `f-${f.name}`;
          const err = errors[f.name];
          if (f.type === "checkbox") {
            return (
              <label key={f.name} className={f.className ?? "flex items-center gap-2 text-sm text-slate-700"}>
                <input id={fid} type="checkbox" className="h-4 w-4 rounded border-slate-300" checked={Boolean(values[f.name])} onChange={(e) => set(f.name, e.target.checked)} />
                {f.label}
                {err && <span className="text-xs text-red-600">{err.join(" ")}</span>}
              </label>
            );
          }
          return (
            <Field key={f.name} label={f.label} htmlFor={fid} required={"required" in f && f.required} hint={f.hint} error={err}
              className={f.className ?? (f.type === "textarea" || f.type === "list" ? "sm:col-span-2" : undefined)}>
              {f.type === "select" ? (
                <Select id={fid} invalid={!!err} value={String(values[f.name])} onChange={(e) => set(f.name, e.target.value)}>
                  {f.options.map((o) => <option key={o.value} value={o.value}>{o.label}</option>)}
                </Select>
              ) : f.type === "textarea" || f.type === "list" ? (
                <Textarea id={fid} invalid={!!err} placeholder={f.placeholder} value={String(values[f.name])} onChange={(e) => set(f.name, e.target.value)} />
              ) : (
                <Input id={fid} invalid={!!err} type={f.type} placeholder={f.placeholder} className={"uppercase" in f && f.uppercase ? "uppercase" : undefined}
                  value={String(values[f.name])} onChange={(e) => set(f.name, e.target.value)} />
              )}
            </Field>
          );
        })}
        <button type="submit" className="hidden" aria-hidden tabIndex={-1} />
      </form>
    </Modal>
  );
}

/** Delete helper: confirm, call DELETE, surface 409 conflict messages from the API. */
export function useDeleter(invalidate: string[][]) {
  const qc = useQueryClient();
  const toast = useToast();
  return async (endpoint: string, label: string) => {
    if (!confirm(`Delete ${label}?`)) return;
    try {
      await api(endpoint, { method: "DELETE" });
      invalidate.forEach((k) => qc.invalidateQueries({ queryKey: k }));
      toast(`Deleted ${label}`);
    } catch (e) {
      toast((e as Error).message, "error");
    }
  };
}
