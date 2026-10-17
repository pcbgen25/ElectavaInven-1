"use client";

import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { useCallback, useMemo } from "react";

/** List state (search, filters, page, ordering) synced to the URL so views are shareable/bookmarkable. */
export function useListState(defaults: { ordering?: string; pageSize?: number } = {}) {
  const router = useRouter();
  const pathname = usePathname();
  const params = useSearchParams();

  const state = useMemo(
    () => ({
      search: params.get("search") ?? "",
      page: Number(params.get("page") ?? "1") || 1,
      pageSize: Number(params.get("page_size") ?? defaults.pageSize ?? 25) || 25,
      ordering: params.get("ordering") ?? defaults.ordering ?? "",
      filters: Object.fromEntries(
        [...params.entries()].filter(([k]) => !["search", "page", "page_size", "ordering"].includes(k)),
      ) as Record<string, string>,
    }),
    [params, defaults.ordering, defaults.pageSize],
  );

  const update = useCallback(
    (patch: Record<string, string | number | null | undefined>, resetPage = true) => {
      const next = new URLSearchParams(params.toString());
      for (const [k, v] of Object.entries(patch)) {
        if (v === null || v === undefined || v === "") next.delete(k);
        else next.set(k, String(v));
      }
      if (resetPage && !("page" in patch)) next.delete("page");
      const qs = next.toString();
      router.replace(qs ? `${pathname}?${qs}` : pathname, { scroll: false });
    },
    [params, pathname, router],
  );

  const query = useMemo(
    () => ({
      search: state.search || undefined,
      page: state.page,
      page_size: state.pageSize,
      ordering: state.ordering || undefined,
      ...state.filters,
    }),
    [state],
  );

  return { ...state, update, query };
}
