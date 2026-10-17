"use client";

import { useQuery } from "@tanstack/react-query";
import Link from "next/link";

import { api } from "@/lib/api";
import type { StockTransaction } from "@/lib/types";

interface StockSummary {
  stock_rows: number;
  components: number;
  warehouses: number;
  total_on_hand: string | number;
  total_reserved: string | number;
  total_available: string | number;
  out_of_stock: number;
  low_stock: number;
  in_stock: number;
  active_reservations: number;
}

export default function InventoryDashboard() {
  const { data: summary, isLoading: loadingSummary } = useQuery<StockSummary>({
    queryKey: ["stock", "summary"],
    queryFn: () => api<StockSummary>("/inventory/stock/summary/"),
  });
  const { data: transactions, isLoading: loadingTxns } = useQuery({
    queryKey: ["transactions"],
    queryFn: () => api<{ results: StockTransaction[] }>("/inventory/transactions/"),
  });

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-3xl font-bold tracking-tight">Inventory Dashboard</h1>
        <div className="space-x-2">
          <Link href="/inventory/stock" className="rounded bg-blue-600 px-4 py-2 text-white hover:bg-blue-700">
            View All Stock
          </Link>
          <Link href="/inventory/warehouses" className="rounded bg-gray-200 px-4 py-2 text-gray-800 hover:bg-gray-300">
            Warehouses
          </Link>
        </div>
      </div>

      <div className="grid grid-cols-1 gap-4 md:grid-cols-4">
        <div className="rounded border bg-white p-4 shadow dark:border-zinc-800 dark:bg-zinc-950">
          <p className="text-sm font-medium text-gray-500">Unique Components in Stock</p>
          <p className="text-2xl font-bold">{loadingSummary ? "..." : (summary?.components ?? 0)}</p>
        </div>
        <div className="rounded border bg-white p-4 shadow dark:border-zinc-800 dark:bg-zinc-950">
          <p className="text-sm font-medium text-gray-500">Total Stock On Hand</p>
          <p className="text-2xl font-bold text-blue-600">{loadingSummary ? "..." : (summary?.total_on_hand ?? 0)}</p>
        </div>
        <div className="rounded border bg-white p-4 shadow dark:border-zinc-800 dark:bg-zinc-950">
          <p className="text-sm font-medium text-gray-500">Total Reserved</p>
          <p className="text-2xl font-bold text-yellow-600">{loadingSummary ? "..." : (summary?.total_reserved ?? 0)}</p>
        </div>
        <div className="rounded border bg-white p-4 shadow dark:border-zinc-800 dark:bg-zinc-950">
          <p className="text-sm font-medium text-gray-500">Total Available</p>
          <p className="text-2xl font-bold text-green-600">{loadingSummary ? "..." : (summary?.total_available ?? 0)}</p>
        </div>
      </div>

      <div className="mt-8">
        <h2 className="mb-4 text-xl font-bold">Recent Transactions</h2>
        <div className="overflow-x-auto rounded border bg-white shadow dark:border-zinc-800 dark:bg-zinc-950">
          <table className="min-w-full text-sm">
            <thead className="border-b bg-gray-50 dark:border-zinc-800 dark:bg-zinc-900">
              <tr>
                <th className="px-4 py-3 text-left">Date</th>
                <th className="px-4 py-3 text-left">Type</th>
                <th className="px-4 py-3 text-left">Component</th>
                <th className="px-4 py-3 text-left">Warehouse</th>
                <th className="px-4 py-3 text-left">Qty</th>
                <th className="px-4 py-3 text-left">User</th>
              </tr>
            </thead>
            <tbody className="divide-y dark:divide-zinc-800">
              {loadingTxns ? (
                <tr>
                  <td colSpan={6} className="px-4 py-4 text-center">
                    Loading...
                  </td>
                </tr>
              ) : (
                transactions?.results?.slice(0, 10).map((txn) => (
                  <tr key={txn.id}>
                    <td className="px-4 py-3">{new Date(txn.timestamp).toLocaleString()}</td>
                    <td className="px-4 py-3 font-medium">{txn.transaction_type}</td>
                    <td className="px-4 py-3">{txn.component_mpn}</td>
                    <td className="px-4 py-3">
                      {txn.warehouse_code} {txn.location_code && `/ ${txn.location_code}`}
                    </td>
                    <td className="px-4 py-3">{txn.quantity}</td>
                    <td className="px-4 py-3">{txn.performed_by_name}</td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
