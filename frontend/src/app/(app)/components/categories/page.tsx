"use client";

import { useQuery } from "@tanstack/react-query";
import { ChevronRight, FolderTree, Pencil, Plus, Trash2 } from "lucide-react";
import Link from "next/link";
import { useMemo, useState } from "react";

import { CrudModal, useDeleter, type FieldSpec } from "@/components/masterdata/crud-modal";
import { Button } from "@/components/ui/button";
import { Badge, Card, EmptyState, ErrorState, PageHeader, Spinner } from "@/components/ui/primitives";
import { api } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { categoryTreeOptions, useCategories } from "@/lib/queries";
import type { Category, DataType, SpecDefinition } from "@/lib/types";
import { cn } from "@/lib/utils";

const DATA_TYPES: { value: DataType; label: string }[] = [
  { value: "STRING", label: "Text" },
  { value: "INTEGER", label: "Integer" },
  { value: "DECIMAL", label: "Decimal" },
  { value: "BOOLEAN", label: "Yes / No" },
  { value: "ENUM", label: "Choice list" },
];

const SPEC_FIELDS: FieldSpec[] = [
  { name: "name", label: "Name", type: "text", required: true, placeholder: "e.g. Capacitance" },
  { name: "key", label: "Key", type: "text", required: true, placeholder: "e.g. capacitance", hint: "Stable machine key (lowercase, underscores)." },
  { name: "data_type", label: "Data type", type: "select", options: DATA_TYPES, hint: "Cannot change once components have values." },
  { name: "unit", label: "Unit", type: "text", placeholder: "e.g. F, Ω, V, W" },
  { name: "enum_choices", label: "Choices (choice list only)", type: "list", placeholder: "One per line, e.g.\nX7R\nC0G\nX5R" },
  { name: "sort_order", label: "Sort order", type: "number" },
  { name: "help_text", label: "Help text", type: "text", className: "sm:col-span-2" },
  { name: "use_si_prefix", label: "Accept SI prefixes (100n, 4k7)", type: "checkbox" },
  { name: "is_required", label: "Required", type: "checkbox" },
  { name: "is_active", label: "Active", type: "checkbox" },
];

const INVALIDATE = [["categories"], ["components"]];

export default function CategoriesPage() {
  const { can } = useAuth();
  const canManage = can("masterdata.manage");
  const { data: categories, isLoading, error, refetch } = useCategories();
  const [selectedId, setSelectedId] = useState<number | null>(null);
  const [editCat, setEditCat] = useState<Category | null | undefined>(undefined);
  const [newParent, setNewParent] = useState<number | null>(null);
  const [editSpec, setEditSpec] = useState<SpecDefinition | null | undefined>(undefined);
  const del = useDeleter(INVALIDATE);

  const tree = useMemo(() => categoryTreeOptions(categories), [categories]);
  const selected = categories?.find((c) => c.id === selectedId) ?? null;

  const defs = useQuery({
    queryKey: ["categories", selectedId, "spec-defs", true],
    queryFn: () => api<SpecDefinition[]>(`categories/${selectedId}/specification-definitions`, { query: { include_inactive: true } }),
    enabled: !!selectedId,
  });

  const catFields: FieldSpec[] = useMemo(() => [
    { name: "name", label: "Name", type: "text", required: true, placeholder: "e.g. Capacitors" },
    { name: "code", label: "Code (part number prefix)", type: "text", required: true, uppercase: true, placeholder: "e.g. CAP", hint: "Used for new internal PNs (CAP-00001). Locked once components use it." },
    { name: "parent", label: "Parent", type: "select", options: [{ value: "", label: "— top level —" }, ...tree.filter((o) => o.id !== editCat?.id).map((o) => ({ value: String(o.id), label: o.label }))] },
    { name: "sort_order", label: "Sort order", type: "number" },
    { name: "description", label: "Description", type: "textarea" },
  ], [tree, editCat]);

  if (isLoading) return <Spinner />;
  if (error) return <ErrorState message={(error as Error).message} onRetry={() => refetch()} />;

  return (
    <>
      <PageHeader title="Categories" subtitle="Category tree and the specification fields each category defines"
        actions={canManage && <Button onClick={() => { setNewParent(null); setEditCat(null); }}><Plus className="h-4 w-4" /> Add category</Button>} />

      <div className="grid gap-4 lg:grid-cols-5">
        <Card title="Tree" className="lg:col-span-2">
          {!tree.length ? <EmptyState title="No categories" /> : (
            <ul className="-mx-2 space-y-0.5">
              {tree.map((o) => {
                const c = categories!.find((x) => x.id === o.id)!;
                return (
                  <li key={o.id}>
                    <button onClick={() => setSelectedId(o.id)} style={{ paddingLeft: `${0.5 + o.depth * 1.1}rem` }}
                      className={cn("flex w-full items-center gap-2 rounded px-2 py-1.5 text-left text-sm", selectedId === o.id ? "bg-blue-50 text-blue-800" : "hover:bg-slate-50")}>
                      {o.depth > 0 ? <ChevronRight className="h-3 w-3 text-slate-300" /> : <FolderTree className="h-3.5 w-3.5 text-slate-400" />}
                      <span className="flex-1 truncate">{c.name}</span>
                      <span className="pn text-xs text-slate-500">{c.code}</span>
                      <span className="w-8 text-right text-xs text-slate-400">{c.component_count}</span>
                    </button>
                  </li>
                );
              })}
            </ul>
          )}
        </Card>

        <div className="space-y-4 lg:col-span-3">
          {!selected ? (
            <Card><p className="text-sm text-slate-500">Select a category to view its details and specification definitions.</p></Card>
          ) : (
            <>
              <Card title={selected.full_path} actions={canManage && (
                <div className="flex gap-1">
                  <Button size="sm" variant="ghost" onClick={() => { setNewParent(selected.id); setEditCat(null); }}><Plus className="h-3.5 w-3.5" /> Sub-category</Button>
                  <Button size="sm" variant="ghost" aria-label="Edit category" onClick={() => setEditCat(selected)}><Pencil className="h-3.5 w-3.5" /></Button>
                  <Button size="sm" variant="ghost" aria-label="Delete category" onClick={async () => { await del(`categories/${selected.id}`, selected.name); setSelectedId(null); }}><Trash2 className="h-3.5 w-3.5" /></Button>
                </div>
              )}>
                <dl className="grid grid-cols-2 gap-3 text-sm sm:grid-cols-3">
                  <div><dt className="text-xs uppercase text-slate-500">PN prefix</dt><dd className="pn">{selected.code}-#####</dd></div>
                  <div><dt className="text-xs uppercase text-slate-500">Components</dt><dd><Link className="text-blue-700 hover:underline" href={`/components?category=${selected.id}`}>{selected.component_count}</Link></dd></div>
                  <div className="col-span-2 sm:col-span-1"><dt className="text-xs uppercase text-slate-500">Description</dt><dd>{selected.description || "—"}</dd></div>
                </dl>
              </Card>

              <Card title="Specification definitions" actions={canManage && <Button size="sm" variant="secondary" onClick={() => setEditSpec(null)}><Plus className="h-3.5 w-3.5" /> Add field</Button>}>
                {defs.isLoading ? <Spinner /> : defs.error ? <ErrorState message={(defs.error as Error).message} /> : !defs.data?.length ? (
                  <p className="text-sm text-slate-500">No specification fields. Sub-categories inherit fields from their parents.</p>
                ) : (
                  <div className="-mx-4 overflow-x-auto">
                    <table className="w-full text-sm">
                      <thead className="bg-slate-50 text-left text-xs uppercase text-slate-500">
                        <tr><th className="px-4 py-2">Field</th><th className="px-2 py-2">Type</th><th className="px-2 py-2">Unit</th><th className="px-2 py-2">Flags</th><th className="px-4 py-2" /></tr>
                      </thead>
                      <tbody className="divide-y divide-slate-100">
                        {defs.data.map((d) => {
                          const inherited = d.category !== selected.id;
                          return (
                            <tr key={d.id} className={cn(!d.is_active && "opacity-50")}>
                              <td className="px-4 py-2">
                                <div className="font-medium text-slate-900">{d.name}</div>
                                <div className="pn text-xs text-slate-400">{d.key}{inherited && ` · inherited from ${d.category_name}`}</div>
                              </td>
                              <td className="px-2 py-2 text-slate-600">
                                {DATA_TYPES.find((t) => t.value === d.data_type)?.label}
                                {d.data_type === "ENUM" && <div className="text-xs text-slate-400">{d.enum_choices.join(", ")}</div>}
                              </td>
                              <td className="px-2 py-2">{d.unit || "—"}{d.use_si_prefix && <span className="ml-1 text-xs text-slate-400">(SI)</span>}</td>
                              <td className="px-2 py-2"><div className="flex flex-wrap gap-1">
                                {d.is_required && <Badge tone="amber">Required</Badge>}
                                {!d.is_active && <Badge>Inactive</Badge>}
                              </div></td>
                              <td className="px-4 py-2 text-right whitespace-nowrap">
                                {canManage && !inherited && (
                                  <>
                                    <Button size="sm" variant="ghost" aria-label={`Edit ${d.name}`} onClick={() => setEditSpec(d)}><Pencil className="h-3.5 w-3.5" /></Button>
                                    <Button size="sm" variant="ghost" aria-label={`Delete ${d.name}`} onClick={() => del(`specification-definitions/${d.id}`, d.name)}><Trash2 className="h-3.5 w-3.5" /></Button>
                                  </>
                                )}
                              </td>
                            </tr>
                          );
                        })}
                      </tbody>
                    </table>
                  </div>
                )}
              </Card>
            </>
          )}
        </div>
      </div>

      <CrudModal open={editCat !== undefined} onClose={() => setEditCat(undefined)} title={editCat ? `Edit ${editCat.name}` : "Add category"}
        endpoint="categories" id={editCat?.id} fields={catFields} invalidate={INVALIDATE}
        initial={editCat ?? { parent: newParent, sort_order: 0 }} />
      {selected && (
        <CrudModal open={editSpec !== undefined} onClose={() => setEditSpec(undefined)} title={editSpec ? `Edit field ${editSpec.name}` : `Add field to ${selected.name}`}
          endpoint="specification-definitions" id={editSpec?.id} fields={SPEC_FIELDS} invalidate={INVALIDATE}
          extraPayload={editSpec ? undefined : { category: selected.id }}
          initial={editSpec ?? { data_type: "STRING", is_active: true, sort_order: 0 }} />
      )}
    </>
  );
}
