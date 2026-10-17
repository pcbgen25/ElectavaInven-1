export interface DataTableColumn<T> {
  header: string;
  accessorKey?: string;
  key?: string;
  cell?: (row: T) => React.ReactNode;
  render?: (val: unknown, row: T) => React.ReactNode;
}

export function DataTable<T>({
  columns,
  data,
}: {
  columns: DataTableColumn<T>[];
  data: T[];
}) {
  const resolveValue = (row: T, path?: string): unknown => {
    if (!path) return null;
    if (path.includes(".")) {
      return path
        .split(".")
        .reduce<unknown>(
          (o, segment) => (o && typeof o === "object" ? (o as Record<string, unknown>)[segment] : undefined),
          row,
        );
    }
    return row && typeof row === "object" ? (row as Record<string, unknown>)[path] : null;
  };

  return (
    <div className="overflow-x-auto rounded-lg border border-slate-200 bg-white dark:border-zinc-800 dark:bg-zinc-950">
      <table className="min-w-full text-left text-sm">
        <thead className="border-b border-slate-200 bg-slate-50 dark:border-zinc-800 dark:bg-zinc-900">
          <tr>
            {columns.map((col, i) => (
              <th key={i} className="px-4 py-3 font-medium text-slate-700 dark:text-zinc-300">
                {col.header}
              </th>
            ))}
          </tr>
        </thead>
        <tbody className="divide-y divide-slate-200 dark:divide-zinc-800">
          {!data || data.length === 0 ? (
            <tr>
              <td colSpan={columns.length} className="p-4 text-center text-slate-500">
                No records found.
              </td>
            </tr>
          ) : (
            data.map((row, i) => (
              <tr key={i} className="hover:bg-slate-50 dark:hover:bg-zinc-900/50">
                {columns.map((col, j) => {
                  const keyPath = col.accessorKey ?? col.key;
                  const val = resolveValue(row, keyPath);
                  const content = col.cell
                    ? col.cell(row)
                    : col.render
                      ? col.render(val, row)
                      : (val as React.ReactNode);
                  return (
                    <td key={j} className="px-4 py-3 text-slate-900 dark:text-slate-100">
                      {content}
                    </td>
                  );
                })}
              </tr>
            ))
          )}
        </tbody>
      </table>
    </div>
  );
}
