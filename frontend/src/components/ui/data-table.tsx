export function DataTable({ columns, data }: { columns: any[], data: any[] }) {
  return (
    <div className="overflow-x-auto rounded-lg border border-slate-200 dark:border-zinc-800 bg-white dark:bg-zinc-950">
      <table className="min-w-full text-sm text-left">
        <thead className="bg-slate-50 dark:bg-zinc-900 border-b border-slate-200 dark:border-zinc-800">
          <tr>
            {columns.map((col, i) => (
              <th key={i} className="px-4 py-3 font-medium text-slate-700 dark:text-zinc-300">{col.header}</th>
            ))}
          </tr>
        </thead>
        <tbody className="divide-y divide-slate-200 dark:divide-zinc-800">
          {data?.length === 0 ? (
            <tr><td colSpan={columns.length} className="p-4 text-center text-slate-500">No records found.</td></tr>
          ) : (
            data?.map((row, i) => (
              <tr key={i} className="hover:bg-slate-50 dark:hover:bg-zinc-900/50">
                {columns.map((col, j) => (
                  <td key={j} className="px-4 py-3 text-slate-900 dark:text-slate-100">
                    {col.cell ? col.cell(row) : (col.accessorKey.includes('.') ? col.accessorKey.split('.').reduce((o:any, i:any) => o?.[i], row) : row[col.accessorKey])}
                  </td>
                ))}
              </tr>
            ))
          )}
        </tbody>
      </table>
    </div>
  );
}
