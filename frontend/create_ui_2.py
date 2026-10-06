import os

inventory_page = """'use client';
import { useQuery } from '@tanstack/react-query';
import { api } from '@/lib/api';
import { InventoryItem, StockTransaction } from '@/lib/types';
import Link from 'next/link';

export default function InventoryDashboard() {
  const { data: stock, isLoading: loadingStock } = useQuery({
    queryKey: ['stock'],
    queryFn: () => api<{results: InventoryItem[]}>('/inventory/stock/')
  });
  const { data: transactions, isLoading: loadingTxns } = useQuery({
    queryKey: ['transactions'],
    queryFn: () => api<{results: StockTransaction[]}>('/inventory/transactions/')
  });

  const totalItems = stock?.results?.length || 0;
  const totalQuantity = stock?.results?.reduce((acc, item) => acc + parseFloat(item.quantity_on_hand), 0) || 0;
  const totalReserved = stock?.results?.reduce((acc, item) => acc + parseFloat(item.quantity_reserved), 0) || 0;
  const totalAvailable = totalQuantity - totalReserved;

  return (
    <div className="space-y-6">
      <div className="flex justify-between items-center">
        <h1 className="text-3xl font-bold tracking-tight">Inventory Dashboard</h1>
        <div className="space-x-2">
            <Link href="/inventory/stock" className="px-4 py-2 bg-blue-600 text-white rounded hover:bg-blue-700">View All Stock</Link>
            <Link href="/inventory/warehouses" className="px-4 py-2 bg-gray-200 text-gray-800 rounded hover:bg-gray-300">Warehouses</Link>
        </div>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        <div className="p-4 bg-white rounded shadow border">
          <p className="text-sm text-gray-500 font-medium">Total Unique Items</p>
          <p className="text-2xl font-bold">{loadingStock ? '...' : totalItems}</p>
        </div>
        <div className="p-4 bg-white rounded shadow border">
          <p className="text-sm text-gray-500 font-medium">Total Stock On Hand</p>
          <p className="text-2xl font-bold text-blue-600">{loadingStock ? '...' : totalQuantity}</p>
        </div>
        <div className="p-4 bg-white rounded shadow border">
          <p className="text-sm text-gray-500 font-medium">Total Reserved</p>
          <p className="text-2xl font-bold text-yellow-600">{loadingStock ? '...' : totalReserved}</p>
        </div>
        <div className="p-4 bg-white rounded shadow border">
          <p className="text-sm text-gray-500 font-medium">Total Available</p>
          <p className="text-2xl font-bold text-green-600">{loadingStock ? '...' : totalAvailable}</p>
        </div>
      </div>

      <div className="mt-8">
        <h2 className="text-xl font-bold mb-4">Recent Transactions</h2>
        <div className="bg-white rounded shadow border overflow-x-auto">
          <table className="min-w-full text-sm">
            <thead className="bg-gray-50 border-b">
              <tr>
                <th className="px-4 py-3 text-left">Date</th>
                <th className="px-4 py-3 text-left">Type</th>
                <th className="px-4 py-3 text-left">Component</th>
                <th className="px-4 py-3 text-left">Warehouse</th>
                <th className="px-4 py-3 text-left">Qty</th>
                <th className="px-4 py-3 text-left">User</th>
              </tr>
            </thead>
            <tbody className="divide-y">
              {loadingTxns ? (
                <tr><td colSpan={6} className="px-4 py-4 text-center">Loading...</td></tr>
              ) : (
                transactions?.results?.slice(0, 10).map((txn) => (
                  <tr key={txn.id}>
                    <td className="px-4 py-3">{new Date(txn.timestamp).toLocaleString()}</td>
                    <td className="px-4 py-3 font-medium">{txn.transaction_type}</td>
                    <td className="px-4 py-3">{txn.component_mpn}</td>
                    <td className="px-4 py-3">{txn.warehouse_code} {txn.location_code && `/ ${txn.location_code}`}</td>
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
"""

stock_page = """'use client';
import { useQuery } from '@tanstack/react-query';
import { api } from '@/lib/api';
import { InventoryItem } from '@/lib/types';
import { DataTable } from '@/components/ui/data-table';
import Link from 'next/link';
import { useState } from 'react';

export default function StockList() {
  const [page, setPage] = useState(1);
  const { data, isLoading } = useQuery({
    queryKey: ['stock', page],
    queryFn: () => api<{count: number; results: InventoryItem[]}>(`/inventory/stock/?page=${page}`)
  });

  const columns = [
    { key: 'component_mpn', header: 'Component MPN' },
    { key: 'warehouse_code', header: 'Warehouse' },
    { key: 'location_code', header: 'Location' },
    { key: 'quantity_on_hand', header: 'On Hand' },
    { key: 'quantity_reserved', header: 'Reserved' },
    { key: 'quantity_available', header: 'Available' },
    { key: 'minimum_stock', header: 'Min Stock' },
  ];

  return (
    <div className="space-y-6">
      <div className="flex justify-between items-center">
        <h1 className="text-2xl font-bold">Inventory Stock</h1>
        <div className="space-x-2">
            <Link href="/inventory/transactions" className="px-4 py-2 bg-gray-100 text-gray-800 rounded border hover:bg-gray-200">History</Link>
            <Link href="/inventory/stock/receive" className="px-4 py-2 bg-blue-600 text-white rounded hover:bg-blue-700">Receive Stock</Link>
        </div>
      </div>
      
      {isLoading ? (
          <div>Loading stock data...</div>
      ) : (
          <DataTable 
            data={data?.results || []} 
            columns={columns} 
          />
      )}
    </div>
  );
}
"""

transactions_page = """'use client';
import { useQuery } from '@tanstack/react-query';
import { api } from '@/lib/api';
import { StockTransaction } from '@/lib/types';
import { DataTable } from '@/components/ui/data-table';
import { useState } from 'react';

export default function TransactionList() {
  const [page, setPage] = useState(1);
  const { data, isLoading } = useQuery({
    queryKey: ['transactions', page],
    queryFn: () => api<{count: number; results: StockTransaction[]}>(`/inventory/transactions/?page=${page}`)
  });

  const columns = [
    { key: 'timestamp', header: 'Date', render: (val: any) => new Date(val).toLocaleString() },
    { key: 'transaction_type', header: 'Type' },
    { key: 'component_mpn', header: 'Component MPN' },
    { key: 'warehouse_code', header: 'Warehouse' },
    { key: 'location_code', header: 'Location' },
    { key: 'quantity', header: 'Quantity' },
    { key: 'reason', header: 'Reason' },
    { key: 'performed_by_name', header: 'User' },
  ];

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold">Transaction History</h1>
      {isLoading ? (
          <div>Loading transactions...</div>
      ) : (
          <DataTable 
            data={data?.results || []} 
            columns={columns} 
          />
      )}
    </div>
  );
}
"""

with open('src/app/(app)/inventory/page.tsx', 'w') as f:
    f.write(inventory_page)
with open('src/app/(app)/inventory/stock/page.tsx', 'w') as f:
    f.write(stock_page)
with open('src/app/(app)/inventory/transactions/page.tsx', 'w') as f:
    f.write(transactions_page)
