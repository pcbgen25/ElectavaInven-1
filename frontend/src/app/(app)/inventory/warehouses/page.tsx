'use client';
import { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { api, ApiError, FieldErrors } from '@/lib/api';
import { Warehouse } from '@/lib/types';
import { DataTable } from '@/components/ui/data-table';
import { Button } from '@/components/ui/button';
import { Field, Input, Textarea } from '@/components/ui/form';

export default function WarehouseList() {
  const queryClient = useQueryClient();
  const { data, isLoading } = useQuery({
    queryKey: ['warehouses'],
    queryFn: () => api<{results: Warehouse[]}>('/inventory/warehouses/')
  });

  const [editing, setEditing] = useState<Partial<Warehouse> | null>(null);
  const [errors, setErrors] = useState<FieldErrors>({});

  const mutation = useMutation({
    mutationFn: (warehouse: Partial<Warehouse>) => {
      if (warehouse.id) {
        return api<Warehouse>(`/inventory/warehouses/${warehouse.id}/`, {
          method: 'PATCH',
          body: warehouse,
        });
      }
      return api<Warehouse>('/inventory/warehouses/', {
        method: 'POST',
        body: warehouse,
      });
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['warehouses'] });
      setEditing(null);
      setErrors({});
    },
    onError: (error: Error) => {
      if (error instanceof ApiError) {
        setErrors(error.fieldErrors);
      }
    }
  });

  const handleSubmit = (e: React.FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    if (editing) mutation.mutate(editing);
  };

  const columns = [
    { accessorKey: 'code', header: 'Code' },
    { accessorKey: 'name', header: 'Name' },
    { accessorKey: 'description', header: 'Description' },
    { accessorKey: 'is_active', header: 'Active', cell: (row: Warehouse) => row.is_active ? 'Yes' : 'No' },
    {
      header: 'Actions',
      cell: (row: Warehouse) => (
        <Button variant="ghost" size="sm" onClick={() => { setEditing(row); setErrors({}); }}>Edit</Button>
      )
    }
  ];

  return (
    <div className="space-y-6">
      <div className="flex justify-between items-center">
        <h1 className="text-2xl font-bold">Warehouses</h1>
        {!editing && (
          <Button onClick={() => { setEditing({ is_active: true }); setErrors({}); }}>Add Warehouse</Button>
        )}
      </div>

      {editing ? (
        <form onSubmit={handleSubmit} className="p-4 bg-white rounded shadow border space-y-4 max-w-xl">
          <h2 className="text-xl font-bold">{editing.id ? 'Edit Warehouse' : 'New Warehouse'}</h2>
          
          <Field label="Code" htmlFor="code" error={errors.code}>
            <Input 
              id="code" 
              value={editing.code || ''} 
              onChange={e => setEditing({...editing, code: e.target.value})} 
              invalid={!!errors.code} 
            />
          </Field>
          
          <Field label="Name" htmlFor="name" error={errors.name}>
            <Input 
              id="name" 
              value={editing.name || ''} 
              onChange={e => setEditing({...editing, name: e.target.value})} 
              invalid={!!errors.name} 
            />
          </Field>
          
          <Field label="Address" htmlFor="address" error={errors.address}>
            <Textarea 
              id="address" 
              value={editing.address || ''} 
              onChange={e => setEditing({...editing, address: e.target.value})} 
              invalid={!!errors.address} 
            />
          </Field>
          
          <Field label="Description" htmlFor="description" error={errors.description}>
            <Textarea 
              id="description" 
              value={editing.description || ''} 
              onChange={e => setEditing({...editing, description: e.target.value})} 
              invalid={!!errors.description} 
            />
          </Field>

          <div className="flex items-center gap-2 mt-4">
            <input 
              type="checkbox" 
              id="is_active" 
              checked={editing.is_active ?? true} 
              onChange={e => setEditing({...editing, is_active: e.target.checked})} 
            />
            <label htmlFor="is_active" className="text-sm">Active</label>
            {errors.is_active && <span className="text-xs text-red-500">{errors.is_active.join(', ')}</span>}
          </div>
          
          {errors.non_field_errors && (
            <div className="text-red-500 text-sm">{errors.non_field_errors.join(', ')}</div>
          )}

          <div className="flex gap-2">
            <Button type="submit" loading={mutation.isPending}>Save</Button>
            <Button variant="secondary" onClick={() => setEditing(null)}>Cancel</Button>
          </div>
        </form>
      ) : (
        isLoading ? (
            <div>Loading warehouses...</div>
        ) : (
            <DataTable 
              data={data?.results || []} 
              columns={columns} 
            />
        )
      )}
    </div>
  );
}
