"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { FileUp, GitCompare, Plus } from "lucide-react";
import Link from "next/link";
import { useParams } from "next/navigation";
import { useState } from "react";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import { DataTable } from "@/components/ui/data-table";
import { Field, Input, Textarea } from "@/components/ui/form";
import { DescriptionList, ErrorState, Modal, Spinner } from "@/components/ui/primitives";
import { ApiError, api } from "@/lib/api";
import type { BOM, BOMRevision } from "@/lib/types";

export default function BomDetail() {
  const params = useParams();
  const bomId = String(params.id || "");
  const qc = useQueryClient();
  const [newRevOpen, setNewRevOpen] = useState(false);
  const [revForm, setRevForm] = useState({ revision_number: "", revision_name: "", description: "" });
  const [errors, setErrors] = useState<Record<string, string[]>>({});

  const { data: bom, isLoading, error } = useQuery<BOM>({
    queryKey: ["boms", bomId],
    queryFn: () => api<BOM>(`boms/${bomId}/`),
  });

  const createRev = useMutation({
    mutationFn: () =>
      api<BOMRevision>("bom-revisions/", {
        method: "POST",
        body: {
          bom: Number(bomId),
          revision_number: revForm.revision_number,
          revision_name: revForm.revision_name,
          description: revForm.description,
        },
      }),
    onSuccess: () => {
      toast.success("Revision created");
      setNewRevOpen(false);
      setRevForm({ revision_number: "", revision_name: "", description: "" });
      setErrors({});
      qc.invalidateQueries({ queryKey: ["boms", bomId] });
    },
    onError: (err: unknown) => {
      if (err instanceof ApiError) {
        setErrors(err.fieldErrors);
        toast.error(err.message);
      } else {
        toast.error("Failed to create revision");
      }
    },
  });

  if (isLoading)
    return (
      <div className="mt-10 flex justify-center">
        <Spinner />
      </div>
    );
  if (error || !bom) return <ErrorState message="Failed to load BOM." />;

  return (
    <div className="space-y-6">
      <div className="flex items-start justify-between">
        <div>
          <h1 className="text-3xl font-bold text-slate-900 dark:text-white">{bom.name}</h1>
          <p className="mt-1 text-slate-500">{bom.description || `Project ID: ${bom.project}`}</p>
        </div>
        <div className="flex flex-wrap gap-2">
          <Button onClick={() => setNewRevOpen(true)}>
            <Plus className="mr-2 h-4 w-4" /> New Revision
          </Button>
          <Link href={`/bom/${bom.id}/import`}>
            <Button variant="secondary">
              <FileUp className="mr-2 h-4 w-4" /> Import KiCad CSV
            </Button>
          </Link>
          <Link href={`/bom-revisions/compare?bom=${bom.id}`}>
            <Button variant="secondary">
              <GitCompare className="mr-2 h-4 w-4" /> Compare
            </Button>
          </Link>
        </div>
      </div>

      <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
        <div className="rounded-xl border bg-white p-4 dark:border-zinc-800 dark:bg-zinc-950">
          <h2 className="mb-4 text-lg font-semibold text-slate-900 dark:text-white">BOM Details</h2>
          <DescriptionList
            items={[
              { label: "Status", value: <span className="font-medium text-emerald-600">{bom.status}</span> },
              { label: "Revisions", value: String(bom.revisions?.length ?? 0) },
              { label: "Created At", value: new Date(bom.created_at).toLocaleDateString() },
            ]}
          />
        </div>
      </div>

      <div className="rounded-xl border bg-white p-4 dark:border-zinc-800 dark:bg-zinc-950">
        <h2 className="mb-4 text-lg font-semibold text-slate-900 dark:text-white">Revision History</h2>
        <DataTable
          columns={[
            {
              header: "Revision",
              accessorKey: "revision_number",
              cell: (r: BOMRevision) => (
                <Link href={`/bom-revisions/${r.id}`} className="font-bold text-emerald-600 hover:underline">
                  {r.revision_number}
                </Link>
              ),
            },
            {
              header: "Status",
              accessorKey: "status",
              cell: (r: BOMRevision) => (
                <span
                  className={`rounded px-2 py-1 text-xs font-semibold ${
                    r.status === "RELEASED"
                      ? "bg-blue-100 text-blue-800 dark:bg-blue-900 dark:text-blue-200"
                      : "bg-slate-100 text-slate-800 dark:bg-zinc-800 dark:text-zinc-200"
                  }`}
                >
                  {r.status}
                </span>
              ),
            },
            {
              header: "Date",
              accessorKey: "created_at",
              cell: (r: BOMRevision) => new Date(r.created_at).toLocaleDateString(),
            },
          ]}
          data={bom.revisions}
        />
      </div>

      <Modal
        open={newRevOpen}
        onClose={() => setNewRevOpen(false)}
        title="New BOM Revision"
        footer={
          <>
            <Button variant="secondary" onClick={() => setNewRevOpen(false)}>
              Cancel
            </Button>
            <Button onClick={() => createRev.mutate()} loading={createRev.isPending}>
              Create Revision
            </Button>
          </>
        }
      >
        <div className="space-y-4">
          <Field label="Revision Number" htmlFor="rev-num" required error={errors.revision_number}>
            <Input
              id="rev-num"
              placeholder="e.g. REV A"
              value={revForm.revision_number}
              onChange={(e) => setRevForm({ ...revForm, revision_number: e.target.value })}
            />
          </Field>
          <Field label="Revision Name" htmlFor="rev-name" error={errors.revision_name}>
            <Input
              id="rev-name"
              placeholder="e.g. Initial Prototype"
              value={revForm.revision_name}
              onChange={(e) => setRevForm({ ...revForm, revision_name: e.target.value })}
            />
          </Field>
          <Field label="Description" htmlFor="rev-desc" error={errors.description}>
            <Textarea
              id="rev-desc"
              value={revForm.description}
              onChange={(e) => setRevForm({ ...revForm, description: e.target.value })}
            />
          </Field>
        </div>
      </Modal>
    </div>
  );
}
