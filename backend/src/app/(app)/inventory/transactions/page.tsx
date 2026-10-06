'use client';
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
