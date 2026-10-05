"use client";

import { ArrowDown, ArrowUp, ChevronLeft, ChevronRight, Columns3, Download, Search } from "lucide-react";
import Link from "next/link";
import { useEffect, useRef, useState } from "react";

import { Button } from "@/components/ui/button";
import { EmptyState, ErrorState, Spinner } from "@/components/ui/primitives";
import { cn } from "@/lib/utils";

export interface Column<T> {
  key: string;
  header: string;
  render: (row: T) => React.ReactNode;
  /** Server ordering field; omit for unsortable columns. */
  sortKey?: string;
  /** Plain-text value used for CSV export. */
  csv?: (row: T) => string | number | null | undefined;
  hiddenByDefault?: boolean;
  className?: string;
}

interface Props<T> {
  id: string; // used to persist column visibility
  columns: Column<T>[];
  rows: T[] | undefined;
  count: number;
  page: number;
  pageSize: number;
  ordering: string;
  loading: boolean;
  error?: string | null;
  onRetry?: () => void;
  search?: string;
  onSearch?: (value: string) => void;
  searchPlaceholder?: string;
  onOrdering: (ordering: string) => void;
  onPage: (page: number) => void;
  onPageSize?: (size: number) => void;
  rowHref?: (row: T) => string;
  rowKey: (row: T) => string | number;
  mobileCard?: (row: T) => React.ReactNode;
  toolbar?: React.ReactNode;
  onExport?: () => Promise<T[]>;
  exportName?: string;
  empty?: React.ReactNode;
}

export function DataTable<T>(props: Props<T>) {
  const { columns, rows, count, page, pageSize, ordering, loading, rowHref, rowKey } = props;
  const [hidden, setHidden] = useState<Set<string>>(() => new Set(columns.filter((c) => c.hiddenByDefault).map((c) => c.key)));
  const [colMenu, setColMenu] = useState(false);
  const [exporting, setExporting] = useState(false);
  const [searchText, setSearchText] = useState(props.search ?? "");
  const menuRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const saved = localStorage.getItem(`dt-cols:${props.id}`);
    // eslint-disable-next-line react-hooks/set-state-in-effect -- hydrate persisted preference once on mount
    if (saved) setHidden(new Set(JSON.parse(saved) as string[]));
  }, [props.id]);

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect -- keep input in sync when URL changes (back/forward)
    setSearchText(props.search ?? "");
  }, [props.search]);

  // Debounced search → URL
  const { onSearch } = props;
  useEffect(() => {
    if (!onSearch || searchText === (props.search ?? "")) return;
    const t = setTimeout(() => onSearch(searchText.trim()), 300);
    return () => clearTimeout(t);
  }, [searchText, onSearch, props.search]);

  useEffect(() => {
    const close = (e: MouseEvent) => menuRef.current && !menuRef.current.contains(e.target as Node) && setColMenu(false);
    document.addEventListener("mousedown", close);
    return () => document.removeEventListener("mousedown", close);
  }, []);

  const toggleCol = (key: string) => {
    const next = new Set(hidden);
    if (next.has(key)) next.delete(key);
    else next.add(key);
    setHidden(next);
    localStorage.setItem(`dt-cols:${props.id}`, JSON.stringify([...next]));
  };

  const visible = columns.filter((c) => !hidden.has(c.key));
  const pages = Math.max(1, Math.ceil(count / pageSize));
  const from = count === 0 ? 0 : (page - 1) * pageSize + 1;
  const to = Math.min(count, page * pageSize);

  const sortBy = (key?: string) => {
    if (!key) return;
    props.onOrdering(ordering === key ? `-${key}` : ordering === `-${key}` ? "" : key);
  };

  const doExport = async () => {
    if (!props.onExport) return;
    setExporting(true);
    try {
      const all = await props.onExport();
      const { toCsv, downloadText } = await import("@/lib/utils");
      const cols = visible.filter((c) => c.csv);
      downloadText(
        `${props.exportName ?? props.id}-${new Date().toISOString().slice(0, 10)}.csv`,
        toCsv(cols.map((c) => c.header), all.map((r) => cols.map((c) => c.csv!(r)))),
      );
    } finally {
      setExporting(false);
    }
  };

  return (
    <div className="rounded-lg border border-slate-200 bg-white">
      <div className="flex flex-col gap-2 border-b border-slate-100 p-3 lg:flex-row lg:items-center">
        {props.onSearch && (
          <div className="relative flex-1">
            <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-400" />
            <input
              type="search"
              value={searchText}
              onChange={(e) => setSearchText(e.target.value)}
              placeholder={props.searchPlaceholder ?? "Search…"}
              aria-label="Search"
              className="h-9 w-full rounded-md border border-slate-300 pl-9 pr-3 text-sm focus:border-blue-500 focus:outline-none focus:ring-2 focus:ring-blue-500/40"
            />
          </div>
        )}
        <div className="flex flex-wrap items-center gap-2">
          {props.toolbar}
          <div className="relative hidden md:block" ref={menuRef}>
            <Button variant="secondary" size="sm" onClick={() => setColMenu((v) => !v)} aria-expanded={colMenu}>
              <Columns3 className="h-3.5 w-3.5" /> Columns
            </Button>
            {colMenu && (
              <div className="absolute right-0 z-20 mt-1 w-48 rounded-md border border-slate-200 bg-white p-1 shadow-lg">
                {columns.map((c) => (
                  <label key={c.key} className="flex cursor-pointer items-center gap-2 rounded px-2 py-1.5 text-sm hover:bg-slate-50">
                    <input type="checkbox" checked={!hidden.has(c.key)} onChange={() => toggleCol(c.key)} />
                    {c.header}
                  </label>
                ))}
              </div>
            )}
          </div>
          {props.onExport && (
            <Button variant="secondary" size="sm" onClick={doExport} loading={exporting} disabled={count === 0}>
              {!exporting && <Download className="h-3.5 w-3.5" />} CSV
            </Button>
          )}
        </div>
      </div>

      {props.error ? (
        <div className="p-4"><ErrorState message={props.error} onRetry={props.onRetry} /></div>
      ) : loading && !rows ? (
        <Spinner />
      ) : !rows || rows.length === 0 ? (
        props.empty ?? <EmptyState title="No records found" description={props.search ? "Try a different search term or clear filters." : undefined} />
      ) : (
        <>
          {/* Desktop table */}
          <div className={cn("hidden overflow-x-auto md:block", loading && "opacity-60")}>
            <table className="w-full text-left text-sm">
              <thead className="bg-slate-50 text-xs uppercase tracking-wide text-slate-500">
                <tr>
                  {visible.map((c) => {
                    const active = ordering.replace("-", "") === c.sortKey;
                    return (
                      <th key={c.key} scope="col" className={cn("whitespace-nowrap px-3 py-2 font-medium", c.className)}
                        aria-sort={active ? (ordering.startsWith("-") ? "descending" : "ascending") : undefined}>
                        {c.sortKey ? (
                          <button className="inline-flex items-center gap-1 hover:text-slate-800" onClick={() => sortBy(c.sortKey)}>
                            {c.header}
                            {active && (ordering.startsWith("-") ? <ArrowDown className="h-3 w-3" /> : <ArrowUp className="h-3 w-3" />)}
                          </button>
                        ) : c.header}
                      </th>
                    );
                  })}
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {rows.map((r) => (
                  <tr key={rowKey(r)} className="hover:bg-slate-50">
                    {visible.map((c, i) => (
                      <td key={c.key} className={cn("px-3 py-2 align-top", c.className)}>
                        {i === 0 && rowHref ? <Link href={rowHref(r)} className="font-medium text-blue-700 hover:underline">{c.render(r)}</Link> : c.render(r)}
                      </td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          {/* Mobile cards */}
          <ul className={cn("divide-y divide-slate-100 md:hidden", loading && "opacity-60")}>
            {rows.map((r) => (
              <li key={rowKey(r)}>
                {rowHref ? (
                  <Link href={rowHref(r)} className="block px-3 py-3 active:bg-slate-50">{props.mobileCard ? props.mobileCard(r) : visible[0]?.render(r)}</Link>
                ) : (
                  <div className="px-3 py-3">{props.mobileCard ? props.mobileCard(r) : visible[0]?.render(r)}</div>
                )}
              </li>
            ))}
          </ul>
        </>
      )}

      <div className="flex flex-col items-center justify-between gap-2 border-t border-slate-100 px-3 py-2 text-xs text-slate-500 sm:flex-row">
        <span>{count > 0 ? `${from}–${to} of ${count}` : "0 results"}</span>
        <div className="flex items-center gap-2">
          {props.onPageSize && (
            <select aria-label="Rows per page" value={pageSize} onChange={(e) => props.onPageSize!(Number(e.target.value))}
              className="h-8 rounded border border-slate-300 bg-white px-2 text-xs">
              {[25, 50, 100].map((n) => <option key={n} value={n}>{n} / page</option>)}
            </select>
          )}
          <Button variant="secondary" size="sm" disabled={page <= 1} onClick={() => props.onPage(page - 1)} aria-label="Previous page">
            <ChevronLeft className="h-4 w-4" />
          </Button>
          <span className="tabular-nums">{page} / {pages}</span>
          <Button variant="secondary" size="sm" disabled={page >= pages} onClick={() => props.onPage(page + 1)} aria-label="Next page">
            <ChevronRight className="h-4 w-4" />
          </Button>
        </div>
      </div>
    </div>
  );
}
