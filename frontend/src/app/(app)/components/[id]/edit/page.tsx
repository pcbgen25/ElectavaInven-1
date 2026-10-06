"use client";

import { useQuery } from "@tanstack/react-query";
import Link from "next/link";
import { useParams } from "next/navigation";

import { ComponentForm } from "@/components/components/component-form";
import { ErrorState, Forbidden, PageHeader, Spinner } from "@/components/ui/primitives";
import { api } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import type { ComponentDetail } from "@/lib/types";

export default function EditComponentPage() {
  const { id } = useParams<{ id: string }>();
  const { can } = useAuth();
  const { data, isLoading, error, refetch } = useQuery<any>({
    queryKey: ["component", id],
    queryFn: () => api<ComponentDetail>(`components/${id}`),
  });

  if (!can("component.edit")) return <Forbidden permission="component.edit" />;
  if (isLoading) return <Spinner />;
  if (error || !data) return <ErrorState message={(error as Error)?.message ?? "Component not found."} onRetry={() => refetch()} />;

  return (
    <>
      <PageHeader
        title={<>Edit <span className="pn">{data.internal_part_number}</span></>}
        subtitle={<><Link href="/components" className="text-blue-700 hover:underline">Components</Link> / <Link href={`/components/${data.id}`} className="text-blue-700 hover:underline">{data.internal_part_number}</Link> / Edit</>}
      />
      {/* key forces a fresh form if the record is refetched with new data */}
      <ComponentForm key={data.updated_at} component={data} />
    </>
  );
}
