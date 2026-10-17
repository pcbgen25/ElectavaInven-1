"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { useState } from "react";

import { Button } from "@/components/ui/button";
import { Field, Input, Select, Textarea } from "@/components/ui/form";
import { ErrorState } from "@/components/ui/primitives";
import { useToast } from "@/components/ui/toast";
import { ApiError, type Paginated, api } from "@/lib/api";

interface ComponentOption {
  id: number;
  internal_part_number: string;
  mpn: string;
  name: string;
}

interface WarehouseOption {
  id: number;
  code: string;
  name: string;
}

interface LocationOption {
  id: number;
  code: string;
  name: string;
  warehouse: number;
}

interface SelectOpt {
  value: string | number;
  label: string;
}

export default function OperationPage() {
  const router = useRouter();
  const params = useParams();
  const operation = String(params.operation || "receive");
  const queryClient = useQueryClient();
  const toast = useToast();

  const [formData, setFormData] = useState<Record<string, string>>({
    direction: "IN",
    reference_type: "PROJECT",
  });
  const [errors, setErrors] = useState<Record<string, string[]>>({});
  const [generalError, setGeneralError] = useState<string | null>(null);

  const { data: components } = useQuery({
    queryKey: ["components", "options"],
    queryFn: async () =>
      (await api<Paginated<ComponentOption>>("components", { query: { page_size: 500 } })).results,
  });

  const { data: warehouses } = useQuery({
    queryKey: ["warehouses", "options"],
    queryFn: async () =>
      (await api<Paginated<WarehouseOption>>("inventory/warehouses", { query: { page_size: 500 } })).results,
  });

  const { data: locations } = useQuery({
    queryKey: ["locations", "options"],
    queryFn: async () =>
      (await api<Paginated<LocationOption>>("inventory/locations", { query: { page_size: 500 } })).results,
  });

  const mutation = useMutation({
    mutationFn: (payload: Record<string, unknown>) =>
      api(`inventory/operations/${operation}`, { method: "POST", body: payload }),
    onSuccess: () => {
      toast(`Stock ${operation} completed successfully.`, "success");
      queryClient.invalidateQueries({ queryKey: ["stock"] });
      queryClient.invalidateQueries({ queryKey: ["transactions"] });
      queryClient.invalidateQueries({ queryKey: ["dashboard"] });
      router.push("/inventory/stock");
    },
    onError: (err) => {
      if (err instanceof ApiError) {
        setErrors(err.fieldErrors);
        setGeneralError(err.message);
        toast(err.message, "error");
      } else {
        setGeneralError("An unexpected error occurred.");
        toast("An unexpected error occurred.", "error");
      }
    },
  });

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    setErrors({});
    setGeneralError(null);
    const cleaned: Record<string, unknown> = {};
    for (const [k, v] of Object.entries(formData)) {
      if (v !== "" && v !== undefined) {
        if (["component", "warehouse", "location", "from_warehouse", "from_location", "to_warehouse", "to_location", "project", "bom_revision"].includes(k)) {
          cleaned[k] = Number(v);
        } else {
          cleaned[k] = v;
        }
      }
    }
    mutation.mutate(cleaned);
  };

  const handleChange = (e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement | HTMLTextAreaElement>) => {
    const { name, value } = e.target;
    setFormData((prev) => ({ ...prev, [name]: value }));
  };

  const titleMap: Record<string, string> = {
    receive: "Receive Stock",
    issue: "Issue Stock",
    adjust: "Adjust Stock",
    transfer: "Transfer Stock",
    reserve: "Reserve Stock",
  };

  const title = titleMap[operation] || "Inventory Operation";

  const renderField = (
    name: string,
    label: string,
    type: "text" | "number" | "select" | "textarea" = "text",
    options?: SelectOpt[],
    required = false,
  ) => {
    const error = errors[name];
    if (type === "select") {
      return (
        <Field label={label} htmlFor={name} error={error} required={required}>
          <Select id={name} name={name} value={formData[name] || ""} onChange={handleChange} invalid={!!error} required={required}>
            <option value="">Select...</option>
            {options?.map((opt) => (
              <option key={opt.value} value={opt.value}>
                {opt.label}
              </option>
            ))}
          </Select>
        </Field>
      );
    }
    if (type === "textarea") {
      return (
        <Field label={label} htmlFor={name} error={error} required={required}>
          <Textarea id={name} name={name} value={formData[name] || ""} onChange={handleChange} invalid={!!error} required={required} />
        </Field>
      );
    }
    return (
      <Field label={label} htmlFor={name} error={error} required={required}>
        <Input id={name} name={name} type={type} step="any" value={formData[name] || ""} onChange={handleChange} invalid={!!error} required={required} />
      </Field>
    );
  };

  const componentOptions: SelectOpt[] =
    components?.map((c) => ({ value: c.id, label: `${c.internal_part_number} — ${c.mpn || c.name}` })) || [];
  const warehouseOptions: SelectOpt[] =
    warehouses?.map((w) => ({ value: w.id, label: `${w.code} — ${w.name}` })) || [];
  const locationsFor = (whKey: string): SelectOpt[] => {
    const whId = Number(formData[whKey]);
    return (
      locations
        ?.filter((l) => !whId || l.warehouse === whId)
        .map((l) => ({ value: l.id, label: `${l.code}${l.name ? ` — ${l.name}` : ""}` })) || []
    );
  };

  return (
    <div className="mx-auto max-w-2xl space-y-6">
      <div className="flex items-center gap-4">
        <Link href="/inventory/stock" className="text-sm text-slate-500 hover:text-slate-900 dark:text-slate-400 dark:hover:text-white">
          &larr; Back to Stock
        </Link>
        <h1 className="text-2xl font-bold text-slate-900 dark:text-white">{title}</h1>
      </div>

      <form onSubmit={handleSubmit} className="space-y-4 rounded-lg border border-slate-200 bg-white p-6 shadow-sm dark:border-zinc-800 dark:bg-zinc-950">
        {generalError && <ErrorState message={generalError} />}

        {renderField("component", "Component", "select", componentOptions, true)}

        {operation === "transfer" ? (
          <>
            <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
              {renderField("from_warehouse", "From Warehouse", "select", warehouseOptions, true)}
              {renderField("from_location", "From Location", "select", locationsFor("from_warehouse"))}
            </div>
            <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
              {renderField("to_warehouse", "To Warehouse", "select", warehouseOptions, true)}
              {renderField("to_location", "To Location", "select", locationsFor("to_warehouse"))}
            </div>
          </>
        ) : (
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
            {renderField("warehouse", "Warehouse", "select", warehouseOptions, true)}
            {renderField("location", "Location", "select", locationsFor("warehouse"))}
          </div>
        )}

        {operation === "adjust" &&
          renderField(
            "direction",
            "Direction",
            "select",
            [
              { value: "IN", label: "IN (Increase Stock)" },
              { value: "OUT", label: "OUT (Decrease Stock)" },
            ],
            true,
          )}

        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
          {renderField("quantity", "Quantity", "number", undefined, true)}
          {renderField("lot_batch", "Lot / Batch")}
        </div>

        {operation === "receive" && (
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
            {renderField("unit_cost", "Unit Cost", "number")}
            {renderField("currency", "Currency (e.g. USD)")}
          </div>
        )}

        {operation === "reserve" && (
          <>
            <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
              {renderField(
                "reference_type",
                "Reference Type",
                "select",
                [
                  { value: "PROJECT", label: "Project" },
                  { value: "BOM_REVISION", label: "BOM Revision" },
                  { value: "WORK_ORDER", label: "Work Order" },
                ],
                false,
              )}
              {renderField("reference_id", "Reference ID", "text", undefined, false)}
            </div>
            <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
              {renderField("project", "Project ID (Optional)", "number")}
              {renderField("bom_revision", "BOM Revision ID (Optional)", "number")}
            </div>
          </>
        )}

        {(operation === "receive" || operation === "issue" || operation === "adjust" || operation === "transfer") && (
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
            {renderField("reference", "Reference Document")}
            {renderField("reason", "Reason", "text", undefined, operation === "adjust")}
          </div>
        )}

        {renderField("notes", "Notes", "textarea")}

        <div className="flex justify-end gap-2 border-t border-slate-100 pt-4 dark:border-zinc-800">
          <Link href="/inventory/stock">
            <Button type="button" variant="secondary">
              Cancel
            </Button>
          </Link>
          <Button type="submit" loading={mutation.isPending}>
            Submit
          </Button>
        </div>
      </form>
    </div>
  );
}
