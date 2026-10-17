"use client";

import { useQuery } from "@tanstack/react-query";

import { api, type Paginated } from "./api";
import type { Category, Manufacturer, Package, SpecDefinition } from "./types";

export const useCategories = () =>
  useQuery({ queryKey: ["categories"], queryFn: () => api<Category[]>("categories"), staleTime: 60_000 });

// Option lists for selects. Capped at 200 entries; a searchable picker will replace these when lists grow.
export const useManufacturerOptions = () =>
  useQuery({
    queryKey: ["manufacturers", "options"],
    queryFn: async () => (await api<Paginated<Manufacturer>>("manufacturers", { query: { page_size: 200, ordering: "name" } })).results,
    staleTime: 60_000,
  });

export const usePackageOptions = () =>
  useQuery({
    queryKey: ["packages", "options"],
    queryFn: async () => (await api<Paginated<Package>>("packages", { query: { page_size: 200, ordering: "name" } })).results,
    staleTime: 60_000,
  });

export const useCategorySpecDefinitions = (categoryId: number | null | undefined, includeInactive = false) =>
  useQuery({
    queryKey: ["categories", categoryId, "spec-defs", includeInactive],
    queryFn: () => api<SpecDefinition[]>(`categories/${categoryId}/specification-definitions`, { query: { include_inactive: includeInactive || undefined } }),
    enabled: !!categoryId,
  });

/** Categories sorted depth-first so a flat <select> reads like a tree. */
export function categoryTreeOptions(categories: Category[] = []): { id: number; label: string; depth: number }[] {
  const byParent = new Map<number | null, Category[]>();
  categories.forEach((c) => byParent.set(c.parent, [...(byParent.get(c.parent) ?? []), c]));
  const out: { id: number; label: string; depth: number }[] = [];
  const ids = new Set(categories.map((c) => c.id));
  const walk = (parent: number | null, depth: number) => {
    for (const c of byParent.get(parent) ?? []) {
      out.push({ id: c.id, label: `${"\u00a0\u00a0".repeat(depth)}${c.name} (${c.code})`, depth });
      walk(c.id, depth + 1);
    }
  };
  walk(null, 0);
  // Orphans whose parent was soft-deleted
  categories.filter((c) => c.parent !== null && !ids.has(c.parent)).forEach((c) => out.push({ id: c.id, label: `${c.name} (${c.code})`, depth: 0 }));
  return out;
}
