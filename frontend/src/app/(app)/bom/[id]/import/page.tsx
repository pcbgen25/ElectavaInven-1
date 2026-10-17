"use client";

import { useMutation, useQuery } from "@tanstack/react-query";
import { UploadCloud } from "lucide-react";
import { useParams, useRouter } from "next/navigation";
import { useState } from "react";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import { DataTable } from "@/components/ui/data-table";
import { api } from "@/lib/api";
import type { BOM } from "@/lib/types";

interface ImportPreviewRow {
  raw: {
    reference?: string;
    mpn?: string;
    value?: string;
    footprint?: string;
    quantity?: number;
  };
  match_status: string;
  component_id?: number | null;
}

export default function KiCadImportWizard() {
  const params = useParams();
  const router = useRouter();
  const bomId = String(params.id || "");
  const [step, setStep] = useState(1);
  const [file, setFile] = useState<File | null>(null);
  const [preview, setPreview] = useState<ImportPreviewRow[]>([]);

  const { data: bom } = useQuery<BOM>({
    queryKey: ["bom", bomId],
    queryFn: () => api<BOM>(`boms/${bomId}/`),
    enabled: !!bomId,
  });

  const uploadMut = useMutation({
    mutationFn: async (f: File) => {
      const formData = new FormData();
      formData.append("file", f);
      return api<{ preview: ImportPreviewRow[] }>(`boms/import_kicad/`, { method: "POST", body: formData });
    },
    onSuccess: (data) => {
      setPreview(data.preview || []);
      setStep(3);
    },
    onError: () => toast.error("Failed to parse CSV"),
  });

  const confirmMut = useMutation({
    mutationFn: async () => {
      return api<{ id: number }>(`boms/confirm_import/`, {
        method: "POST",
        body: {
          project_id: bom?.project ?? 1,
          name: bom?.name ? `${bom.name} (Imported)` : "Imported BOM",
          matched_items: preview,
        },
      });
    },
    onSuccess: (data) => {
      toast.success("BOM Imported!");
      router.push(`/bom/${data.id}`);
    },
    onError: () => toast.error("Failed to confirm BOM import"),
  });

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold text-slate-900 dark:text-white">KiCad BOM Import Wizard</h1>

      <div className="mb-8 flex gap-4">
        {[1, 2, 3, 4, 5].map((s) => (
          <div key={s} className={`h-2 flex-1 rounded-full ${s <= step ? "bg-emerald-500" : "bg-slate-200 dark:bg-zinc-800"}`} />
        ))}
      </div>

      {step === 1 && (
        <div className="flex flex-col items-center justify-center rounded-xl border-2 border-dashed p-12 text-center dark:border-zinc-800">
          <UploadCloud className="mb-4 h-12 w-12 text-slate-400" />
          <h3 className="mb-2 text-lg font-semibold dark:text-white">Upload KiCad CSV</h3>
          <p className="mb-6 text-slate-500">Select your KiCad CSV BOM file to parse and match components.</p>
          <input type="file" accept=".csv" onChange={(e) => setFile(e.target.files?.[0] || null)} className="mb-4" />
          <Button onClick={() => file && uploadMut.mutate(file)} disabled={!file || uploadMut.isPending} loading={uploadMut.isPending}>
            Upload and Parse
          </Button>
        </div>
      )}

      {step === 3 && (
        <div className="space-y-4">
          <h2 className="text-lg font-semibold dark:text-white">Component Matching</h2>
          <DataTable
            columns={[
              { header: "Reference", accessorKey: "raw.reference" },
              { header: "MPN", accessorKey: "raw.mpn" },
              {
                header: "Status",
                accessorKey: "match_status",
                cell: (r: ImportPreviewRow) => {
                  const color =
                    r.match_status === "MATCHED"
                      ? "text-emerald-600"
                      : r.match_status === "UNMATCHED"
                        ? "text-red-500"
                        : "text-amber-500";
                  return <span className={`font-bold ${color}`}>{r.match_status}</span>;
                },
              },
            ]}
            data={preview}
          />
          <div className="mt-4 flex justify-end">
            <Button onClick={() => setStep(4)}>Continue to Review</Button>
          </div>
        </div>
      )}

      {step === 4 && (
        <div className="space-y-4">
          <h2 className="text-lg font-semibold dark:text-white">Review Import</h2>
          <div className="rounded-xl border bg-slate-50 p-6 dark:border-zinc-800 dark:bg-zinc-900">
            <div className="mb-6 grid grid-cols-2 gap-4">
              <div>
                Total Components: <strong>{preview.length}</strong>
              </div>
              <div>
                Matched: <strong className="text-emerald-600">{preview.filter((p) => p.match_status === "MATCHED").length}</strong>
              </div>
              <div>
                Unmatched: <strong className="text-red-500">{preview.filter((p) => p.match_status === "UNMATCHED").length}</strong>
              </div>
            </div>
            <Button onClick={() => confirmMut.mutate()} loading={confirmMut.isPending} className="w-full bg-blue-600 text-white hover:bg-blue-700">
              Confirm and Import BOM
            </Button>
          </div>
        </div>
      )}
    </div>
  );
}
