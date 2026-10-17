'use client';
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
    { accessorKey: 'component_mpn', header: 'Component MPN' },
    { accessorKey: 'warehouse_code', header: 'Warehouse' },
    { accessorKey: 'location_code', header: 'Location' },
    { accessorKey: 'quantity_on_hand', header: 'On Hand' },
    { accessorKey: 'quantity_reserved', header: 'Reserved' },
    { accessorKey: 'quantity_available', header: 'Available' },
    { accessorKey: 'minimum_stock', header: 'Min Stock' },
  ];

  return (
    <div className="space-y-6">
      <div className="flex justify-between items-center">
        <h1 className="text-2xl font-bold">Inventory Stock</h1>
        <div className="space-x-2">
            <Link href="/inventory/transactions" className="px-4 py-2 bg-gray-100 text-gray-800 rounded border hover:bg-gray-200">History</Link>
            <Link href="/inventory/operations/receive" className="px-3 py-2 bg-blue-600 text-white rounded hover:bg-blue-700 text-sm">Receive</Link>
            <Link href="/inventory/operations/issue" className="px-3 py-2 bg-gray-600 text-white rounded hover:bg-gray-700 text-sm">Issue</Link>
            <Link href="/inventory/operations/adjust" className="px-3 py-2 bg-gray-600 text-white rounded hover:bg-gray-700 text-sm">Adjust</Link>
            <Link href="/inventory/operations/transfer" className="px-3 py-2 bg-gray-600 text-white rounded hover:bg-gray-700 text-sm">Transfer</Link>
            <Link href="/inventory/operations/reserve" className="px-3 py-2 bg-yellow-600 text-white rounded hover:bg-yellow-700 text-sm">Reserve</Link>
        </div>
      </div>
      
      {isLoading ? (
          <div>Loading stock data...</div>
      ) : (
          <div className="space-y-4">
            <DataTable 
              data={data?.results || []} 
              columns={columns} 
            />
            <div className="flex gap-2 items-center">
              <button 
                disabled={page === 1} 
                onClick={() => setPage(p => Math.max(1, p - 1))}
                className="px-3 py-1 border rounded disabled:opacity-50"
              >
                Previous
              </button>
              <span className="text-sm">Page {page}</span>
              <button 
                disabled={!data?.count || page * 20 >= data.count}
                onClick={() => setPage(p => p + 1)}
                className="px-3 py-1 border rounded disabled:opacity-50"
              >
                Next
              </button>
            </div>
          </div>
      )}
    </div>
  );
}
