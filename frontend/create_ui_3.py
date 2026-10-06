import os

warehouses_page = """'use client';
import { useQuery } from '@tanstack/react-query';
import { api } from '@/lib/api';
import { Warehouse } from '@/lib/types';
import { DataTable } from '@/components/ui/data-table';

export default function WarehouseList() {
  const { data, isLoading } = useQuery({
    queryKey: ['warehouses'],
    queryFn: () => api<{results: Warehouse[]}>('/inventory/warehouses/')
  });

  const columns = [
    { key: 'code', header: 'Code' },
    { key: 'name', header: 'Name' },
    { key: 'description', header: 'Description' },
    { key: 'is_active', header: 'Active', render: (val: any) => val ? 'Yes' : 'No' },
  ];

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold">Warehouses</h1>
      {isLoading ? (
          <div>Loading warehouses...</div>
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

with open('src/app/(app)/inventory/warehouses/page.tsx', 'w') as f:
    f.write(warehouses_page)
