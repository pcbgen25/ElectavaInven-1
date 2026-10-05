"use client";

import { useQueryClient } from "@tanstack/react-query";
import { Plus, Trash2 } from "lucide-react";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { useFieldArray, useForm, useWatch } from "react-hook-form";

import { Button } from "@/components/ui/button";
import { Field, Input, Select, Textarea } from "@/components/ui/form";
import { Card, ErrorState, Spinner } from "@/components/ui/primitives";
import { useToast } from "@/components/ui/toast";
import { ApiError, api } from "@/lib/api";
import { categoryTreeOptions, useCategories, useCategorySpecDefinitions, useManufacturerOptions, usePackageOptions } from "@/lib/queries";
import { ALIAS_TYPES, LIFECYCLE_LABELS, STATUS_LABELS, type ComponentDetail, type SpecDefinition } from "@/lib/types";

interface FormValues {
  internal_part_number: string;
  category: string;
  name: string;
  mpn: string;
  manufacturer: string;
  package: string;
  status: string;
  lifecycle_status: string;
  is_rohs: string;
  is_reach: string;
  datasheet_url: string;
  description: string;
  notes: string;
  specs: Record<string, string>;
  aliases: { alias: string; alias_type: string }[];
}

const tri = (v: boolean | null | undefined) => (v === true ? "true" : v === false ? "false" : "");
const fromTri = (v: string) => (v === "true" ? true : v === "false" ? false : null);

function initialSpecs(c?: ComponentDetail): Record<string, string> {
  const out: Record<string, string> = {};
  c?.specifications.forEach((s) => {
    if (s.data_type === "DECIMAL") out[s.definition] = s.display_value;
    else if (s.data_type === "BOOLEAN") out[s.definition] = s.value === null ? "" : String(s.value);
    else out[s.definition] = s.value === null ? "" : String(s.value);
  });
  return out;
}

function SpecInput({ def, register, invalid }: { def: SpecDefinition; register: ReturnType<typeof useForm<FormValues>>["register"]; invalid: boolean }) {
  const name = `specs.${def.id}` as const;
  const id = `spec-${def.id}`;
  if (def.data_type === "BOOLEAN") {
    return (
      <Select id={id} invalid={invalid} {...register(name)}>
        <option value="">—</option><option value="true">Yes</option><option value="false">No</option>
      </Select>
    );
  }
  if (def.data_type === "ENUM") {
    return (
      <Select id={id} invalid={invalid} {...register(name)}>
        <option value="">—</option>
        {def.enum_choices.map((c) => <option key={c} value={c}>{c}</option>)}
      </Select>
    );
  }
  const numeric = def.data_type === "DECIMAL" || def.data_type === "INTEGER";
  const placeholder = def.use_si_prefix ? `e.g. ${def.unit === "F" ? "100n, 4u7" : def.unit === "Ω" ? "4k7, 10R" : "100m, 3.3"}` : undefined;
  return <Input id={id} invalid={invalid} suffix={def.unit || undefined} inputMode={numeric && !def.use_si_prefix ? "decimal" : "text"} placeholder={placeholder} {...register(name)} />;
}

export function ComponentForm({ component }: { component?: ComponentDetail }) {
  const isEdit = !!component;
  const router = useRouter();
  const qc = useQueryClient();
  const toast = useToast();
  const [formError, setFormError] = useState<string | null>(null);
  const [specErrors, setSpecErrors] = useState<string[]>([]);
  const { data: categories, isLoading: catLoading } = useCategories();
  const { data: manufacturers } = useManufacturerOptions();
  const { data: packages } = usePackageOptions();

  const { register, handleSubmit, control, setError, formState: { errors, isSubmitting } } = useForm<FormValues>({
    defaultValues: {
      internal_part_number: component?.internal_part_number ?? "",
      category: component ? String(component.category.id) : "",
      name: component?.name ?? "",
      mpn: component?.mpn ?? "",
      manufacturer: component?.manufacturer ? String(component.manufacturer.id) : "",
      package: component?.package ? String(component.package.id) : "",
      status: component?.status ?? "ACTIVE",
      lifecycle_status: component?.lifecycle_status ?? "UNKNOWN",
      is_rohs: tri(component?.is_rohs),
      is_reach: tri(component?.is_reach),
      datasheet_url: component?.datasheet_url ?? "",
      description: component?.description ?? "",
      notes: component?.notes ?? "",
      specs: initialSpecs(component),
      aliases: component?.aliases.map((a) => ({ alias: a.alias, alias_type: a.alias_type })) ?? [],
    },
  });
  const aliases = useFieldArray({ control, name: "aliases" });
  const categoryId = Number(useWatch({ control, name: "category" })) || null;
  const { data: defs, isLoading: defsLoading } = useCategorySpecDefinitions(categoryId, isEdit);
  const selectedCategory = categories?.find((c) => c.id === categoryId);

  const onSubmit = async (v: FormValues) => {
    setFormError(null);
    setSpecErrors([]);
    const payload: Record<string, unknown> = {
      category: Number(v.category),
      name: v.name.trim(),
      mpn: v.mpn.trim(),
      manufacturer: v.manufacturer ? Number(v.manufacturer) : null,
      package: v.package ? Number(v.package) : null,
      status: v.status,
      lifecycle_status: v.lifecycle_status,
      is_rohs: fromTri(v.is_rohs),
      is_reach: fromTri(v.is_reach),
      datasheet_url: v.datasheet_url.trim(),
      description: v.description,
      notes: v.notes,
      specifications: (defs ?? []).map((d) => {
        const raw = v.specs?.[d.id] ?? "";
        return { definition: d.id, value: d.data_type === "BOOLEAN" ? fromTri(raw) : raw };
      }),
      aliases: v.aliases.filter((a) => a.alias.trim()).map((a) => ({ alias: a.alias.trim(), alias_type: a.alias_type })),
    };
    if (!isEdit) payload.internal_part_number = v.internal_part_number.trim();
    try {
      const saved = await api<ComponentDetail>(isEdit ? `components/${component.id}` : "components", { method: isEdit ? "PATCH" : "POST", body: payload });
      qc.invalidateQueries({ queryKey: ["components"] });
      qc.invalidateQueries({ queryKey: ["dashboard"] });
      qc.setQueryData(["component", String(saved.id)], saved);
      toast(isEdit ? `Saved ${saved.internal_part_number}` : `Created ${saved.internal_part_number}`);
      router.push(`/components/${saved.id}`);
    } catch (e) {
      if (!(e instanceof ApiError)) { setFormError("Unexpected error. Please try again."); return; }
      const known = Object.keys(payload).concat("internal_part_number");
      let mapped = false;
      for (const [field, msgs] of Object.entries(e.fieldErrors)) {
        if (field === "specifications") { setSpecErrors(msgs); mapped = true; }
        else if (known.includes(field) && field !== "aliases") { setError(field as keyof FormValues, { message: msgs.join(" ") }); mapped = true; }
      }
      setFormError(mapped ? "Please fix the highlighted fields." : e.message);
    }
  };

  if (catLoading) return <Spinner />;

  return (
    <form onSubmit={handleSubmit(onSubmit)} noValidate className="space-y-4">
      {formError && <ErrorState message={formError} />}
      <Card title="Identification">
        <div className="grid gap-4 md:grid-cols-2">
          <Field label="Category" htmlFor="category" required error={errors.category?.message}
            hint={isEdit ? "Changing category removes specifications that the new category does not define." : undefined}>
            <Select id="category" invalid={!!errors.category} {...register("category", { required: "Select a category." })}>
              <option value="">Select category…</option>
              {categoryTreeOptions(categories).map((o) => <option key={o.id} value={o.id}>{o.label}</option>)}
            </Select>
          </Field>
          <Field label="Internal part number" htmlFor="internal_part_number" error={errors.internal_part_number?.message}
            hint={isEdit ? "Part numbers are permanent." : `Leave blank to auto-generate${selectedCategory ? ` (${selectedCategory.code}-#####)` : ""}.`}>
            <Input id="internal_part_number" className="pn uppercase" disabled={isEdit} invalid={!!errors.internal_part_number}
              placeholder={selectedCategory ? `${selectedCategory.code}-00001` : "Auto"} {...register("internal_part_number", { maxLength: { value: 40, message: "Max 40 characters." } })} />
          </Field>
          <Field label="Name" htmlFor="name" required error={errors.name?.message} className="md:col-span-2">
            <Input id="name" invalid={!!errors.name} placeholder="e.g. CAN Transceiver" {...register("name", { required: "Name is required.", maxLength: { value: 200, message: "Max 200 characters." } })} />
          </Field>
          <Field label="Manufacturer" htmlFor="manufacturer" error={errors.manufacturer?.message}>
            <Select id="manufacturer" invalid={!!errors.manufacturer} {...register("manufacturer")}>
              <option value="">— none / generic —</option>
              {manufacturers?.map((m) => <option key={m.id} value={m.id}>{m.name}</option>)}
            </Select>
          </Field>
          <Field label="Manufacturer part number (MPN)" htmlFor="mpn" error={errors.mpn?.message}>
            <Input id="mpn" className="pn" invalid={!!errors.mpn} placeholder="e.g. TCAN1042HGVDRQ1" {...register("mpn", { maxLength: { value: 100, message: "Max 100 characters." } })} />
          </Field>
          <Field label="Package" htmlFor="package" error={errors.package?.message}>
            <Select id="package" {...register("package")}>
              <option value="">—</option>
              {packages?.map((p) => <option key={p.id} value={p.id}>{p.name}</option>)}
            </Select>
          </Field>
          <div className="grid grid-cols-2 gap-4">
            <Field label="Status" htmlFor="status">
              <Select id="status" {...register("status")}>
                {Object.entries(STATUS_LABELS).map(([v, l]) => <option key={v} value={v}>{l}</option>)}
              </Select>
            </Field>
            <Field label="Lifecycle" htmlFor="lifecycle_status">
              <Select id="lifecycle_status" {...register("lifecycle_status")}>
                {Object.entries(LIFECYCLE_LABELS).map(([v, l]) => <option key={v} value={v}>{l}</option>)}
              </Select>
            </Field>
          </div>
        </div>
      </Card>

      <Card title="Specifications">
        {!categoryId ? <p className="text-sm text-slate-500">Select a category to see its specifications.</p>
          : defsLoading ? <Spinner /> : !defs?.length ? (
            <p className="text-sm text-slate-500">This category has no specification definitions. Add them under Components → Categories.</p>
          ) : (
            <div className="space-y-3">
              {specErrors.length > 0 && <ErrorState message={specErrors.join(" ")} />}
              <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
                {defs.map((d) => (
                  <Field key={d.id} label={`${d.name}${d.is_active ? "" : " (inactive)"}`} htmlFor={`spec-${d.id}`} required={d.is_required}
                    hint={d.help_text || (d.use_si_prefix ? `SI prefixes accepted (p n µ m k M) · base unit ${d.unit}` : undefined)}>
                    <SpecInput def={d} register={register} invalid={specErrors.some((m) => m.startsWith(`${d.name}:`))} />
                  </Field>
                ))}
              </div>
            </div>
          )}
      </Card>

      <Card title="Compliance & documentation">
        <div className="grid gap-4 md:grid-cols-3">
          <Field label="RoHS" htmlFor="is_rohs">
            <Select id="is_rohs" {...register("is_rohs")}><option value="">Unknown</option><option value="true">Yes</option><option value="false">No</option></Select>
          </Field>
          <Field label="REACH" htmlFor="is_reach">
            <Select id="is_reach" {...register("is_reach")}><option value="">Unknown</option><option value="true">Yes</option><option value="false">No</option></Select>
          </Field>
          <Field label="Datasheet URL" htmlFor="datasheet_url" error={errors.datasheet_url?.message} hint="PDF uploads are available on the component page.">
            <Input id="datasheet_url" type="url" invalid={!!errors.datasheet_url} placeholder="https://…"
              {...register("datasheet_url", { pattern: { value: /^https?:\/\/\S+$/i, message: "Enter a full http(s) URL." } })} />
          </Field>
          <Field label="Description" htmlFor="description" className="md:col-span-3"><Textarea id="description" {...register("description")} /></Field>
          <Field label="Notes" htmlFor="notes" className="md:col-span-3"><Textarea id="notes" {...register("notes")} /></Field>
        </div>
      </Card>

      <Card title="Aliases" actions={<Button size="sm" variant="secondary" onClick={() => aliases.append({ alias: "", alias_type: "ALTERNATE_MPN" })}><Plus className="h-3.5 w-3.5" /> Add alias</Button>}>
        {aliases.fields.length === 0 ? <p className="text-sm text-slate-500">Alternate MPNs, legacy PNs or KiCad values used to match this component during BOM import.</p> : (
          <div className="space-y-2">
            {aliases.fields.map((f, i) => (
              <div key={f.id} className="flex gap-2">
                <Input aria-label={`Alias ${i + 1}`} className="pn flex-1" placeholder="Alias" {...register(`aliases.${i}.alias` as const)} />
                <Select aria-label={`Alias ${i + 1} type`} className="w-44 sm:w-56" {...register(`aliases.${i}.alias_type` as const)}>
                  {ALIAS_TYPES.map((t) => <option key={t.value} value={t.value}>{t.label}</option>)}
                </Select>
                <Button variant="ghost" aria-label="Remove alias" onClick={() => aliases.remove(i)}><Trash2 className="h-4 w-4" /></Button>
              </div>
            ))}
          </div>
        )}
      </Card>

      <div className="sticky bottom-16 z-10 -mx-3 flex justify-end gap-2 border-t border-slate-200 bg-white/95 px-3 py-3 backdrop-blur sm:mx-0 sm:rounded-lg sm:border md:bottom-0">
        <Button variant="secondary" onClick={() => router.back()}>Cancel</Button>
        <Button type="submit" loading={isSubmitting}>{isEdit ? "Save changes" : "Create component"}</Button>
      </div>
    </form>
  );
}
