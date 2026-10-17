"use client";

import { useQuery } from "@tanstack/react-query";
import { useState } from "react";

import { DataTable, type DataTableColumn } from "@/components/ui/data-table";
import { api } from "@/lib/api";
import { StockTransaction } from "@/lib/types";

export default function TransactionList() {
  const [page, setPage] = useState(1);
  const { data, isLoading } = useQuery({
    queryKey: ["transactions", page],
    queryFn: () => api<{ count: number; results: StockTransaction[] }>(`/inventory/transactions/?page=${page}`),
  });

  const columns: DataTableColumn<StockTransaction>[] = [
    {
      accessorKey: "timestamp",
      header: "Date",
      cell: (row) => new Date(row.timestamp).toLocaleString(),
    },
    { accessorKey: "transaction_type", header: "Type" },
    { accessorKey: "component_mpn", header: "Component MPN" },
    { accessorKey: "warehouse_code", header: "Warehouse" },
    { accessorKey: "location_code", header: "Location" },
    { accessorKey: "quantity", header: "Quantity" },
    { accessorKey: "reason", header: "Reason" },
    { accessorKey: "performed_by_name", header: "User" },
  ];

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold">Transaction History</h1>
      {isLoading ? (
        <div>Loading transactions...</div>
      ) : (
        <div className="space-y-4">
          <DataTable data={data?.results || []} columns={columns} />
          <div className="flex items-center gap-2">
            <button
              disabled={page === 1}
              onClick={() => setPage((p) => Math.max(1, p - 1))}
              className="rounded border px-3 py-1 disabled:opacity-50"
            >
              Previous
            </button>
            <span className="text-sm">Page {page}</span>
            <button
              disabled={!data?.count || page * 20 >= data.count}
              onClick={() => setPage((p) => p + 1)}
              className="rounded border px-3 py-1 disabled:opacity-50"
            >
              Next
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
