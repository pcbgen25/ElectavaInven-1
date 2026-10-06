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
